import pytest


@pytest.fixture
def app():
    import main
    main.app.testing = True
    return main.app.test_client()


def test_recognize(app):
    r = app.post('/recognize',
                 recording_url='file://./sample.wav')

    assert r.status_code == 200
