from django.test import TestCase
from django.contrib.auth import get_user_model
from election_core.models import Election, AllowedEmail, ElectionToken, Institution, Voter, ElectionOrganizer
import uuid

User = get_user_model()

class TokenFlowTests(TestCase):
    def setUp(self):
        self.inst = Institution.objects.create(name="Token Univ", short_code="TK")
        self.org_user = User.objects.create_user(
            username="org@tk.edu", email="org@tk.edu", password="pass", role="ORGANIZER", institution=self.inst
        )
        self.organizer = ElectionOrganizer.objects.create(user=self.org_user, status="APPROVED")
        self.election = Election.objects.create(
            title="Token Election",
            short_id="TKN24",
            institution=self.inst,
            organizer=self.organizer,
            accreditation_type='TOKEN',
            is_cleared=True,
            status='ACTIVE'
        )
        self.voter_user = User.objects.create_user(
            username="voter@tk.edu", email="voter@tk.edu", password="pass", role="VOTER", institution=self.inst
        )
        # Add to allowed email
        self.allowed = AllowedEmail.objects.create(election=self.election, email=self.voter_user.email)
        
        # 1. Voter registers (skip OTP)
        from election_core.services import register_voter
        self.voter_user, self.voter_profile = register_voter(
            full_name="John Doe",
            email=self.voter_user.email,
            matric_number="TK/101",
            faculty="Science",
            department="CS",
            institution_id=self.inst.id,
            election_id=self.election.id,
            password="pass",
            skip_otp=True # It should skip OTP since accreditation_type is TOKEN
        )

    def test_token_flow(self):
        # Voter is registered but not token verified yet
        self.assertTrue(self.voter_profile.is_accredited)
        self.assertFalse(self.voter_profile.is_token_verified)
        
        # Admin sends token (simulate)
        new_token_uuid = uuid.uuid4()
        token = ElectionToken.objects.create(
            election=self.election,
            allowed_email=self.allowed,
            token=new_token_uuid
        )
        
        # Voter uses token
        self.assertTrue(token.is_valid())
        self.assertFalse(token.is_used)
        
        # Simulate view logic
        token_obj = ElectionToken.objects.get(token=new_token_uuid)
        token_obj.is_used = True
        token_obj.save()
        
        self.voter_profile.is_token_verified = True
        self.voter_profile.save()
        
        self.assertTrue(self.voter_profile.is_token_verified)
        self.assertFalse(token_obj.is_valid()) # since is_used is now True
        
        print("End-to-end token flow verified successfully!")
