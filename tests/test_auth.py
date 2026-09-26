import httpx
import pytest

from twi_scraper.auth import submit_chapter_password
from twi_scraper.downloader import fetch_chapter
from twi_scraper.errors import LockedChapterError

CHAPTER_URL = "https://wanderinginn.com/chapter/"
LOCKED_HTML = """
<html><head><title>Protected: 1.05</title></head><body>
<article class="twi-article">
<p>This content is password-protected.</p>
<form action="/wp-login.php?action=postpass" method="post">
<input type="hidden" name="redirect_to" value="https://wanderinginn.com/chapter/">
<input type="password" name="post_password">
</form>
</article></body></html>
"""
UNLOCKED_HTML = """
<html><head><title>1.05</title></head><body>
<article class="twi-article"><p>The chapter is readable.</p></article>
</body></html>
"""
HYBRID_HTML = """
<html><head><title>1.01</title></head><body>
<article class="twi-article"><h2>Patreon Exclusive</h2><p>Unlock with Patreon</p></article>
<script>
const formHtml = '<div id="hybrid-password-form">'
  + '<form method="post"><input type="text" name="hybrid_pass"'
  + ' placeholder="Enter password" /></form></div>';
</script></body></html>
"""


def test_password_form_unlocks_chapter_in_the_same_session():
	requests = []

	def handler(request):
		requests.append(request)
		if request.method == "POST":
			assert str(request.url) == "https://wanderinginn.com/wp-login.php?action=postpass"
			assert b"post_password=secret" in request.content
			assert b"redirect_to=" in request.content
			return httpx.Response(302, headers={"set-cookie": "wp-postpass_test=ok; Path=/"})
		if "wp-postpass_test=ok" in request.headers.get("cookie", ""):
			return httpx.Response(200, text=UNLOCKED_HTML)
		return httpx.Response(200, text=LOCKED_HTML)

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		chapter = fetch_chapter(client, CHAPTER_URL, password_provider=lambda url: "secret")

	assert "The chapter is readable." in chapter.markdown
	assert [request.method for request in requests] == ["GET", "POST", "GET"]


def test_javascript_inserted_hybrid_form_unlocks_chapter():
	requests = []

	def handler(request):
		requests.append(request)
		if request.method == "POST":
			assert str(request.url) == CHAPTER_URL
			assert request.content == b"hybrid_pass=secret"
			return httpx.Response(302, headers={"set-cookie": "hybrid_access=ok; Path=/"})
		if "hybrid_access=ok" in request.headers.get("cookie", ""):
			return httpx.Response(200, text=UNLOCKED_HTML)
		return httpx.Response(200, text=HYBRID_HTML)

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		chapter = fetch_chapter(client, CHAPTER_URL, password_provider=lambda url: "secret")

	assert "readable" in chapter.markdown
	assert [request.method for request in requests] == ["GET", "POST", "GET"]


def test_wrong_password_fails_after_one_submission():
	requests = []

	def handler(request):
		requests.append(request)
		return httpx.Response(200, text=LOCKED_HTML)

	with (
		httpx.Client(transport=httpx.MockTransport(handler)) as client,
		pytest.raises(LockedChapterError, match="did not unlock"),
	):
		fetch_chapter(client, CHAPTER_URL, password_provider=lambda url: "wrong")

	assert [request.method for request in requests] == ["GET", "POST", "GET"]


@pytest.mark.parametrize(
	"action",
	[
		"https://other.example/wp-login.php",
		"http://wanderinginn.com/wp-login.php",
		"https://wanderinginn.com.evil.example/wp-login.php",
	],
)
def test_password_is_not_sent_to_unsafe_form_action(action):
	html = LOCKED_HTML.replace("/wp-login.php?action=postpass", action)
	requests = []

	def handler(request):
		requests.append(request)
		return httpx.Response(200, text=html)

	with (
		httpx.Client(transport=httpx.MockTransport(handler)) as client,
		pytest.raises(LockedChapterError, match="unsafe address"),
	):
		fetch_chapter(
			client, CHAPTER_URL, password_provider=lambda url: pytest.fail("Unsafe form prompted")
		)

	assert [request.method for request in requests] == ["GET"]


def test_locked_chapter_without_form_fails_clearly():
	with (
		httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client,
		pytest.raises(LockedChapterError, match="supported password form"),
	):
		submit_chapter_password(
			client,
			CHAPTER_URL,
			"<p>This content is password-protected.</p>",
			lambda: pytest.fail("Missing form prompted"),
		)


def test_unlocked_page_does_not_request_password():
	with httpx.Client(
		transport=httpx.MockTransport(lambda request: httpx.Response(200, text=UNLOCKED_HTML))
	) as client:
		chapter = fetch_chapter(
			client,
			CHAPTER_URL,
			password_provider=lambda url: pytest.fail("Password should not be requested"),
		)
	assert "readable" in chapter.markdown
