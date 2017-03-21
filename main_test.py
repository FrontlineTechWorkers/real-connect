
import os
import unittest

class MainTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["TWILIO_ACCOUNT_SID"] = "TEST"
        os.environ["TWILIO_AUTH_TOKEN"] = "TEST"
        import main
        self.app = main.app.test_client()

    def test_hello(self):
        resp = self.app.post('/', data=dict(CallSid='TEST', From='+85298765432'))
        self.assertIn('<Record', resp.data)
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()