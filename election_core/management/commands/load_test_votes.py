"""
FlashVote Load Test Management Command
=======================================
Simulates N voters casting ballots on a real election.

Usage:
    python manage.py load_test_votes --election JXNO --count 1000
    python manage.py load_test_votes --election JXNO --count 1000 --threads 10
    python manage.py load_test_votes --election JXNO --count 1000 --cleanup

Options:
    --election  : short_id of the election to simulate votes for (required)
    --count     : number of fake voters to create and simulate (default: 100)
    --threads   : number of parallel threads (simulates concurrency) (default: 1)
    --cleanup   : after test, delete all test users/voters created by this run
"""

import time
import uuid
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection


class Command(BaseCommand):
    help = 'Load test: simulate N voters casting votes on a given election.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--election', required=True,
            help='short_id of the election to test against (e.g. JXNO)'
        )
        parser.add_argument(
            '--count', type=int, default=100,
            help='Number of simulated voters (default: 100)'
        )
        parser.add_argument(
            '--threads', type=int, default=1,
            help='Number of concurrent threads (default: 1 = sequential)'
        )
        parser.add_argument(
            '--cleanup', action='store_true',
            help='Delete all test data created by this run after completion'
        )

    def handle(self, *args, **options):
        from election_core.models import Election, Voter, AllowedEmail, Position, Candidate
        from election_core.models import User
        from election_core.voting_logic import cast_vote

        short_id  = options['election']
        count     = options['count']
        threads   = options['threads']
        do_cleanup = options['cleanup']

        # ─── Fetch the election ──────────────────────────────────────
        try:
            election = Election.objects.select_related('organizer', 'institution').get(short_id=short_id)
        except Election.DoesNotExist:
            raise CommandError(f"No election found with short_id='{short_id}'")

        self.stdout.write(self.style.HTTP_INFO(
            f"\n══════════════════════════════════════════════════\n"
            f"  FlashVote Load Test\n"
            f"  Election : {election.title}\n"
            f"  Voters   : {count:,}\n"
            f"  Threads  : {threads}\n"
            f"══════════════════════════════════════════════════"
        ))

        # ─── Check positions & candidates ───────────────────────────
        positions = list(Position.objects.filter(election=election).prefetch_related('candidates'))
        if not positions:
            raise CommandError("This election has no positions. Please add positions and candidates first.")

        for pos in positions:
            if not pos.candidates.exists():
                raise CommandError(f"Position '{pos.title}' has no candidates.")

        self.stdout.write(f"  Positions: {len(positions)} | Status: {election.status}")

        if election.status != 'ACTIVE':
            self.stdout.write(self.style.WARNING(
                f"\n  ⚠  Election status is '{election.status}' (not ACTIVE).\n"
                f"     Votes will fail at is_voting_allowed() check.\n"
                f"     To test the DB performance only, the command will bypass\n"
                f"     the status check by calling cast_vote directly with monkeypatching.\n"
                f"     Consider setting election to ACTIVE before running.\n"
            ))

        # ─── Seed test users & voters ────────────────────────────────
        self.stdout.write(f"\n[1/4] Creating {count:,} test users & voters...")
        seed_start = time.perf_counter()

        tag = f"loadtest_{uuid.uuid4().hex[:8]}"  # unique tag for this run
        test_users   = []
        test_voters  = []
        voter_ballots = []  # list of (user, votes_data)

        with transaction.atomic():
            users_to_create = []
            for i in range(count):
                email = f"{tag}_voter_{i:05d}@test.flashvote.local"
                users_to_create.append(User(
                    email=email,
                    username=email,
                    first_name="Test",
                    last_name=f"Voter{i:05d}",
                    role='VOTER',
                ))

            # Test users never log in — skip expensive PBKDF2 password hashing
            for u in users_to_create:
                u.set_unusable_password()

            User.objects.bulk_create(users_to_create, batch_size=500)
            test_users = list(User.objects.filter(email__startswith=tag))

            self.stdout.write(f"    ✓ {len(test_users):,} User accounts created")

            # Add to AllowedEmail
            allowed_emails = [
                AllowedEmail(election=election, email=u.email)
                for u in test_users
            ]
            AllowedEmail.objects.bulk_create(allowed_emails, ignore_conflicts=True, batch_size=500)

            # Create Voter records
            voters_to_create = [
                Voter(
                    user=u,
                    election=election,
                    matric_number=f"{tag}_{i:05d}",
                    faculty="Test Faculty",
                    department="Test Department",
                    is_accredited=True,
                    has_voted=False,
                )
                for i, u in enumerate(test_users)
            ]
            Voter.objects.bulk_create(voters_to_create, batch_size=500)
            test_voters = list(Voter.objects.filter(election=election, matric_number__startswith=tag))

            self.stdout.write(f"    ✓ {len(test_voters):,} Voter records created & accredited")

        # Build ballot data for each voter (random candidate per position)
        for user in test_users:
            votes_data = []
            for pos in positions:
                candidates = list(pos.candidates.all())
                chosen = random.choice(candidates)
                votes_data.append({
                    'position_id': pos.id,
                    'candidate_id': chosen.id,
                })
            voter_ballots.append((user, votes_data))

        seed_elapsed = time.perf_counter() - seed_start
        self.stdout.write(f"    ✓ Seeding complete in {seed_elapsed:.2f}s\n")

        # ─── Cast votes ──────────────────────────────────────────────
        self.stdout.write(f"[2/4] Casting {count:,} votes using {threads} thread(s)...")

        successes = 0
        failures  = 0
        errors    = []
        lock      = threading.Lock()

        def do_vote(user, votes_data):
            nonlocal successes, failures
            try:
                # Temporarily patch is_voting_allowed to skip status check
                original_allowed = election.is_voting_allowed

                def patched_allowed():
                    return True, "Load test bypass"

                election.is_voting_allowed = patched_allowed
                cast_vote(user, election.id, votes_data)
                election.is_voting_allowed = original_allowed

                with lock:
                    successes += 1
            except Exception as e:
                with lock:
                    failures += 1
                    errors.append(str(e))
            finally:
                connection.close()  # Return DB connection to pool after each thread

        vote_start = time.perf_counter()

        if threads == 1:
            # Sequential — show a simple progress bar
            for idx, (user, votes_data) in enumerate(voter_ballots):
                do_vote(user, votes_data)
                if (idx + 1) % 100 == 0:
                    elapsed = time.perf_counter() - vote_start
                    rate = (idx + 1) / elapsed
                    self.stdout.write(
                        f"    → {idx+1:,}/{count:,} votes cast | "
                        f"{rate:.1f} votes/sec | {elapsed:.1f}s elapsed"
                    )
        else:
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(do_vote, user, votes_data): i
                    for i, (user, votes_data) in enumerate(voter_ballots)
                }
                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    if completed % 100 == 0:
                        elapsed = time.perf_counter() - vote_start
                        rate = completed / elapsed
                        self.stdout.write(
                            f"    → {completed:,}/{count:,} votes cast | "
                            f"{rate:.1f} votes/sec | {elapsed:.1f}s elapsed"
                        )

        vote_elapsed = time.perf_counter() - vote_start

        # ─── Results ─────────────────────────────────────────────────
        self.stdout.write(f"\n[3/4] Results\n══════════════════════════════════════════════════")
        rate = count / vote_elapsed if vote_elapsed > 0 else 0

        self.stdout.write(self.style.SUCCESS(f"  ✅ Successful votes  : {successes:,}"))
        if failures:
            self.stdout.write(self.style.ERROR(f"  ❌ Failed votes      : {failures:,}"))
            for e in errors[:5]:
                self.stdout.write(self.style.ERROR(f"     → {e}"))
            if len(errors) > 5:
                self.stdout.write(f"     ... and {len(errors)-5} more errors")

        self.stdout.write(f"  ⏱  Total time        : {vote_elapsed:.2f}s")
        self.stdout.write(f"  🚀 Throughput        : {rate:.1f} votes/second")
        self.stdout.write(f"  📊 Avg per vote      : {(vote_elapsed/count)*1000:.1f}ms")

        projected_4h = int(rate * 3600 * 4)
        self.stdout.write(f"\n  📈 At this rate, system can handle:")
        self.stdout.write(f"     {projected_4h:,} votes in 4 hours")
        if projected_4h >= 20000:
            self.stdout.write(self.style.SUCCESS(f"     ✅ PASSES the 20,000-in-4-hours benchmark!"))
        else:
            self.stdout.write(self.style.WARNING(f"     ⚠  Below 20,000-vote benchmark. Consider adding Gunicorn workers."))

        # ─── Cleanup ─────────────────────────────────────────────────
        if do_cleanup:
            self.stdout.write(f'\n[4/4] Cleaning up test data...')
            with transaction.atomic():
                deleted_users, _ = User.objects.filter(email__startswith=tag).delete()
                self.stdout.write(self.style.SUCCESS(f"  ✓ Removed {deleted_users:,} test users (voters cascade-deleted)"))
        else:
            self.stdout.write(
                f'\n[4/4] Test data NOT cleaned up (omit --cleanup to keep it).\n'
                f'      To clean up manually, delete User records where email starts with: {tag}'
            )

        self.stdout.write(self.style.HTTP_INFO('\n══════════════════════════════════════════════════\n'))
