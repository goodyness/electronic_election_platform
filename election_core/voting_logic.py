from django.db import transaction
from .models import Vote, Voter, Candidate, Election, Position
from .utils import sign_vote, generate_verification_id


def cast_vote(voter_user, election_id, votes_data, ip_address=None, user_agent=None):
    """
    votes_data: list of dicts [{'position_id': 1, 'candidate_id': 5}, ...]

    Optimized for high-concurrency:
    - select_for_update() prevents double-voting race conditions
    - Pre-fetches all positions and candidates in 2 queries (not N+1)
    - Uses bulk_create() to insert all votes in a single DB round-trip
    """
    election = Election.objects.get(id=election_id)

    # 1. Basic checks (outside atomic block — no write needed)
    allowed, reason = election.is_voting_allowed()
    if not allowed:
        raise Exception(reason)

    # Pre-fetch all valid positions and candidates for this election
    # This avoids N individual queries inside the loop (N+1 fix)
    position_ids  = [item['position_id']  for item in votes_data]
    candidate_ids = [item['candidate_id'] for item in votes_data]

    positions  = {p.id: p for p in Position.objects.filter(id__in=position_ids,  election=election)}
    candidates = {c.id: c for c in Candidate.objects.filter(id__in=candidate_ids)}

    with transaction.atomic():
        # 2. Lock the voter row to prevent race conditions (anti-double vote)
        voter = Voter.objects.select_for_update().get(user=voter_user, election=election)

        if voter.has_voted:
            raise Exception("You have already cast your vote in this election.")

        if not voter.is_accredited:
            raise Exception("You are not accredited to vote in this election.")

        # 3. Build and bulk-insert all Vote objects in a single query
        verification_id = generate_verification_id()
        vote_objects = []

        for item in votes_data:
            position  = positions.get(item['position_id'])
            candidate = candidates.get(item['candidate_id'])

            if not position or not candidate:
                raise Exception("Invalid position or candidate in your ballot.")

            # Verify candidate belongs to the right position (integrity check)
            if candidate.position_id != position.id:
                raise Exception("Candidate does not belong to the specified position.")

            signature = sign_vote(election.id, position.id, candidate.id)

            vote_objects.append(Vote(
                election=election,
                position=position,
                candidate=candidate,
                signature=signature,
                verification_id=verification_id,
                ip_address=ip_address,
                user_agent=user_agent,
            ))

        # Single DB insert for all votes (replaces N individual INSERT statements)
        Vote.objects.bulk_create(vote_objects)

        # 4. Mark voter as done (single UPDATE, uses only changed fields)
        voter.has_voted = True
        voter.save(update_fields=['has_voted'])

    # 5. Send receipt email via Celery (outside atomic block — safe after commit)
    from .tasks import send_verification_receipt_task
    send_verification_receipt_task.delay(voter_user.email, election.title, verification_id, election.id)

    return True, f"Your vote has been cast successfully. Your Verification ID is: {verification_id}"
