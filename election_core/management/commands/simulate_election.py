import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from election_core.models import (
    Election, Position, Candidate, AllowedEmail, Vote, 
    SystemConfig, Institution, ElectionOrganizer, User, Voter
)
from datetime import timedelta
import traceback
import uuid

class Command(BaseCommand):
    help = 'Simulates a full election lifecycle for testing and integrity verification.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Election Simulation Suite...'))

        # 1. Setup Institution & User (Fresh Start)
        test_inst_name = "Tactical Training Center"
        Institution.objects.filter(name=test_inst_name).delete()
        inst = Institution.objects.create(name=test_inst_name)
        
        email = 'agrocrestfarm@gmail.com'
        password = 'School123456'
        username = 'agrocrestfarm'
        
        User.objects.filter(username=username).delete()
        User.objects.filter(email=email).delete()
        
        user = User.objects.create(
            username=username,
            email=email,
            first_name='Agro',
            last_name='Crest',
            role='ORGANIZER',
            institution=inst
        )
        user.set_password(password)
        user.save()
        
        self.stdout.write(f"Created fresh organizer: {email}")
        
        profile = ElectionOrganizer.objects.create(user=user, status='APPROVED')
        self.stdout.write(f"Organizer profile approved.")

        # 2. Suppress Emails during simulation
        config = SystemConfig.get_config()
        original_otp = config.enable_otp_emails
        original_receipt = config.enable_receipt_emails
        config.enable_otp_emails = False
        config.enable_receipt_emails = False
        config.save()
        self.stdout.write(self.style.WARNING("Global Email Notifications SUPPRESSED for simulation."))

        try:
            # 3. Create Election
            election_title = f"Integrity Test Election {uuid.uuid4().hex[:6].upper()}"
            election = Election.objects.create(
                organizer=profile,
                institution=inst,
                title=election_title,
                start_time=timezone.now() - timedelta(hours=1),
                end_time=timezone.now() + timedelta(hours=2),
                status='ACTIVE',
                plan='PREMIUM',
                is_voting_enabled=True
            )
            self.stdout.write(self.style.SUCCESS(f"Election Created: {election.title} (ID: {election.short_id})"))

            # 4. Create Positions & Candidates
            pos_data = [
                ('President', ['Alice Smith', 'Bob Johnson']),
                ('Secretary', ['Charlie Brown', 'Dana White'])
            ]
            
            positions = []
            for p_title, c_names in pos_data:
                pos = Position.objects.create(election=election, title=p_title)
                positions.append(pos)
                for name in c_names:
                    Candidate.objects.create(position=pos, full_name=name)
            
            self.stdout.write(f"Created {len(positions)} positions and candidates.")

            # 5. Add 100 Voters
            voter_emails = [f"voter_{i}_{uuid.uuid4().hex[:4]}@example.com" for i in range(1, 101)]
            AllowedEmail.objects.bulk_create([
                AllowedEmail(election=election, email=e) for e in voter_emails
            ])
            self.stdout.write(f"Added 100 voters to the allowed list.")

            # 6. Simulate Voting
            self.stdout.write("Simulating 100 votes...")
            votes_to_create = []
            for i, email in enumerate(voter_emails):
                voter_user, _ = User.objects.get_or_create(email=email, defaults={'role': 'VOTER', 'username': email})
                
                voter_profile = Voter.objects.create(
                    user=voter_user, 
                    election=election,
                    matric_number=f"MAT-{i+1:04d}-{uuid.uuid4().hex[:4].upper()}",
                    faculty='Test Faculty',
                    department='Test Dept',
                    is_accredited=True,
                    has_voted=True
                )

                for pos in positions:
                    candidates = list(pos.candidates.all())
                    chosen = random.choice(candidates)
                    votes_to_create.append(Vote(
                        election=election,
                        position=pos,
                        candidate=chosen,
                        verification_id=f"TEST-{uuid.uuid4().hex[:12].upper()}"
                    ))
            
            Vote.objects.bulk_create(votes_to_create)
            self.stdout.write(self.style.SUCCESS(f"Successfully cast {len(votes_to_create)} votes."))

            # 7. Close and Seal Election
            election.status = 'CLOSED'
            election.save()
            
            from django.core.serializers import serialize
            import hashlib
            
            all_votes = Vote.objects.filter(election=election).order_by('id')
            vote_data = serialize('json', all_votes)
            election.result_hash = hashlib.sha256(vote_data.encode()).hexdigest()
            election.save()

            self.stdout.write(self.style.SUCCESS(f"Election CLOSED and SEALED."))
            self.stdout.write(self.style.SUCCESS(f"FINAL AUDIT HASH: {election.result_hash}"))
            self.stdout.write(f"View results at: /results/{election.short_id}/")

        except Exception:
            self.stderr.write(traceback.format_exc())
        finally:
            config.enable_otp_emails = original_otp
            config.enable_receipt_emails = original_receipt
            config.save()
            self.stdout.write("Global configurations RESTORED.")
