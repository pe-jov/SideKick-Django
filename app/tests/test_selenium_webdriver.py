import os
import time
import unittest
from urllib.parse import urlparse

from django.contrib.auth.hashers import make_password
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone

from app.models import CollaborationRequest, Item, Membership, ResearchSpace, ShareLink, User

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:  # pragma: no cover
    webdriver = None


@unittest.skipIf(webdriver is None, "Selenium is not installed.")
class SeleniumWebDriverTests(StaticLiveServerTestCase):
    """Selenium WebDriver testovi za ključne SideKick korisničke tokove."""

    host = "127.0.0.1"
    wait_timeout = 12

    @classmethod
    def setUpClass(cls):
        try:
            super().setUpClass()
        except PermissionError as exc:
            raise unittest.SkipTest(
                f"Live server could not start in this environment: {exc}"
            ) from exc
        cls.browser = cls._build_browser()
        cls.browser.set_window_size(1440, 1100)

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "browser", None)
        if browser is not None:
            browser.quit()
        super().tearDownClass()

    @classmethod
    def _build_browser(cls):
        browser_name = os.environ.get("SELENIUM_BROWSER", "chrome").strip().lower() or "chrome"
        headless_enabled = os.environ.get("SELENIUM_HEADLESS", "1") != "0"
        try:
            if browser_name == "firefox":
                options = FirefoxOptions()
                if headless_enabled:
                    options.add_argument("-headless")
                return webdriver.Firefox(options=options)

            options = ChromeOptions()
            if headless_enabled:
                options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,1100")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            return webdriver.Chrome(options=options)
        except WebDriverException as exc:
            raise unittest.SkipTest(f"Selenium browser is not available: {exc}") from exc

    def setUp(self):
        now = timezone.now()
        self._extra_browsers = []
        self.wait = WebDriverWait(self.browser, self.wait_timeout)
        self.unique_suffix = now.strftime("%Y%m%d%H%M%S%f")
        self.password = "Sidekick123!"

        self.owner = User.objects.create(
            email=f"owner-{self.unique_suffix}@example.com",
            password_hash=make_password(self.password),
            full_name="Owner User",
            created_at=now,
            updated_at=now,
        )
        self.collaborator = User.objects.create(
            email=f"collaborator-{self.unique_suffix}@example.com",
            password_hash=make_password(self.password),
            full_name="Collaborator User",
            created_at=now,
            updated_at=now,
        )
        self.viewer = User.objects.create(
            email=f"viewer-{self.unique_suffix}@example.com",
            password_hash=make_password(self.password),
            full_name="Viewer User",
            created_at=now,
            updated_at=now,
        )
        self.shared_space = ResearchSpace.objects.create(
            owner=self.owner,
            name=f"Shared Space {self.unique_suffix}",
            description="Initial shared description",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.owner_only_space = ResearchSpace.objects.create(
            owner=self.owner,
            name=f"Owner Space {self.unique_suffix}",
            description="Protected owner-only space",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.share_link = ShareLink.objects.create(
            space=self.shared_space,
            created_by=self.owner,
            token=f"share-{self.unique_suffix}",
            created_at=now,
            expires_at=None,
            is_active=True,
        )
        Membership.objects.create(
            space=self.shared_space,
            user=self.collaborator,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.owner_space_url = reverse("app:space_detail", args=[self.owner_only_space.space_id])
        self.shared_space_url = reverse("app:space_detail", args=[self.shared_space.space_id])
        self.share_access_url = reverse("app:share_link_access", args=[self.share_link.token])

    def tearDown(self):
        for browser in self._extra_browsers:
            browser.quit()

    def spawn_browser(self):
        browser = self._build_browser()
        browser.set_window_size(1440, 1100)
        self._extra_browsers.append(browser)
        return browser

    def make_wait(self, browser):
        return WebDriverWait(browser, self.wait_timeout)

    def absolute_url(self, path):
        return f"{self.live_server_url}{path}"

    def open_path(self, browser, path):
        browser.get(self.absolute_url(path))

    def wait_for_authenticated_state(self, browser, expected):
        expected_value = "true" if expected else "false"
        self.make_wait(browser).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f"[data-authenticated='{expected_value}']"))
        )

    def login(self, browser, email, password, next_path=None):
        path = reverse("app:home") + "?mock=login"
        if next_path:
            path = f"{path}&next={next_path}"
        self.open_path(browser, path)
        wait = self.make_wait(browser)
        wait.until(EC.visibility_of_element_located((By.NAME, "email"))).send_keys(email)
        browser.find_element(By.NAME, "password").send_keys(password)
        browser.find_element(By.CSS_SELECTOR, "form.auth-modal-form button[type='submit']").click()
        self.wait_for_authenticated_state(browser, True)

    def logout(self, browser):
        self.open_path(browser, reverse("app:profile"))
        wait = self.make_wait(browser)
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "form.profile-logout-form button[type='submit']"))
        ).click()
        self.wait_for_authenticated_state(browser, False)

    def create_space(self, browser, name, description):
        self.open_path(browser, f"{reverse('app:home')}?dialog=create-space")
        wait = self.make_wait(browser)
        wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "form[action='/spaces/create/'] input[name='name']"))
        ).send_keys(name)
        browser.find_element(
            By.CSS_SELECTOR, "form[action='/spaces/create/'] textarea[name='description']"
        ).send_keys(description)
        browser.find_element(
            By.CSS_SELECTOR, "form[action='/spaces/create/'] button[type='submit']"
        ).click()
        wait.until(lambda driver: "/spaces/" in driver.current_url)
        self.wait_for_text(browser, By.TAG_NAME, "body", name)
        return ResearchSpace.objects.get(owner=self.owner, name=name)

    def open_space(self, browser, space):
        self.open_path(browser, reverse("app:space_detail", args=[space.space_id]))
        self.make_wait(browser).until(EC.visibility_of_element_located((By.TAG_NAME, "h2")))
        self.wait_for_text(browser, By.TAG_NAME, "body", space.name)

    def create_text_item(self, browser, space, text_value):
        self.open_path(browser, f"{reverse('app:space_detail', args=[space.space_id])}?dialog=add-item")
        wait = self.make_wait(browser)
        field = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "form[data-item-form] textarea[data-item-capture-field]"))
        )
        field.clear()
        field.send_keys(text_value)
        browser.find_element(By.CSS_SELECTOR, "form[data-item-form] button[type='submit']").click()
        self.wait_for_item_card(browser, text_value)

    def open_team_modal(self, browser, space):
        self.open_path(browser, f"{reverse('app:space_detail', args=[space.space_id])}?modal=team")
        self.make_wait(browser).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-overlay-kind='team-modal']"))
        )

    def wait_for_text(self, browser, by, value, text):
        self.make_wait(browser).until(EC.text_to_be_present_in_element((by, value), text))

    def wait_for_item_card(self, browser, text_value):
        xpath = (
            "//article[contains(@class, 'item-card')]"
            f"[@data-content={self.xpath_literal(text_value)}]"
        )
        self.make_wait(browser).until(EC.presence_of_element_located((By.XPATH, xpath)))

    def count_item_cards(self, browser, text_value):
        xpath = (
            "//article[contains(@class, 'item-card')]"
            f"[@data-content={self.xpath_literal(text_value)}]"
        )
        return len(browser.find_elements(By.XPATH, xpath))

    def wait_for_item_count_stable(self, browser, text_value, expected_count, stable_seconds=2.0):
        xpath = (
            "//article[contains(@class, 'item-card')]"
            f"[@data-content={self.xpath_literal(text_value)}]"
        )
        start = {"value": None}

        def condition(driver):
            current_count = len(driver.find_elements(By.XPATH, xpath))
            now = time.monotonic()
            if current_count != expected_count:
                start["value"] = None
                return False
            if start["value"] is None:
                start["value"] = now
                return False
            return (now - start["value"]) >= stable_seconds

        WebDriverWait(browser, self.wait_timeout, poll_frequency=0.25).until(condition)

    def reopen_space_settings(self, browser, space):
        self.open_path(
            browser,
            f"{reverse('app:space_detail', args=[space.space_id])}?dialog=space-settings",
        )
        wait = self.make_wait(browser)
        name_input = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "form[action='/spaces/update/'] input[name='name']"))
        )
        description_input = browser.find_element(
            By.CSS_SELECTOR, "form[action='/spaces/update/'] textarea[name='description']"
        )
        return name_input, description_input

    def require_realtime_socket_support(self):
        self.skipTest(
            "SideKick realtime browser tok koristi ASGI Socket.IO endpoint, dok StaticLiveServerTestCase podiže WSGI test server bez tog endpointa."
        )

    def xpath_literal(self, value):
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"

    def assert_redirected_home(self, browser):
        current_path = urlparse(browser.current_url).path
        self.assertEqual(current_path, reverse("app:home"))
        self.wait_for_authenticated_state(browser, False)

    def test_swd_01_uspesna_prijava_korisnika(self):
        """Uspešna prijava prikazuje početnu stranicu prijavljenog korisnika i sekciju prostora."""
        self.login(self.browser, self.owner.email, self.password)

        self.wait_for_text(self.browser, By.TAG_NAME, "body", "Spaces")
        self.wait_for_text(self.browser, By.TAG_NAME, "body", self.shared_space.name)
        self.assertTrue(
            self.browser.find_elements(By.CSS_SELECTOR, ".space-grid .space-card")
        )

    def test_swd_02_odjava_i_zabrana_pristupa_zasticenom_space_u(self):
        """Nakon odjave korisnik ne može direktno da otvori ranije dostupan zaštićeni prostor."""
        self.login(self.browser, self.owner.email, self.password)
        self.open_space(self.browser, self.owner_only_space)
        protected_url = self.browser.current_url

        self.logout(self.browser)
        self.browser.get(protected_url)

        self.assert_redirected_home(self.browser)
        self.assertFalse(self.browser.find_elements(By.XPATH, f"//h2[normalize-space()={self.xpath_literal(self.owner_only_space.name)}]"))

    def test_swd_03_kreiranje_space_a_i_provera_posle_reload_a(self):
        """Novo kreirani prostor ostaje vidljiv i nakon osvežavanja stranice."""
        self.login(self.browser, self.owner.email, self.password)
        space_name = f"Selenium Created {self.unique_suffix}"
        created_space = self.create_space(self.browser, space_name, "Created from Selenium test.")

        self.open_path(self.browser, reverse("app:home"))
        self.wait_for_text(self.browser, By.TAG_NAME, "body", created_space.name)
        self.browser.refresh()
        self.wait_for_text(self.browser, By.TAG_NAME, "body", created_space.name)
        self.assertTrue(ResearchSpace.objects.filter(space_id=created_space.space_id).exists())

    def test_swd_04_owner_menja_naziv_i_opis_space_a(self):
        """Vlasnik može da izmeni naziv i opis prostora i izmene ostaju sačuvane nakon ponovnog otvaranja."""
        self.login(self.browser, self.owner.email, self.password)
        name_input, description_input = self.reopen_space_settings(self.browser, self.owner_only_space)
        new_name = f"Updated Space {self.unique_suffix}"
        new_description = f"Updated description {self.unique_suffix}"
        name_input.clear()
        name_input.send_keys(new_name)
        description_input.clear()
        description_input.send_keys(new_description)
        self.browser.find_element(
            By.CSS_SELECTOR, "form[action='/spaces/update/'] button[type='submit']"
        ).click()

        self.wait_for_text(self.browser, By.TAG_NAME, "body", "Space updated.")
        self.owner_only_space.refresh_from_db()
        self.open_space(self.browser, self.owner_only_space)
        reopened_name_input, reopened_description_input = self.reopen_space_settings(
            self.browser,
            self.owner_only_space,
        )
        self.assertEqual(reopened_name_input.get_attribute("value"), new_name)
        self.assertEqual(reopened_description_input.get_attribute("value"), new_description)
        self.assertEqual(self.owner_only_space.name, new_name)
        self.assertEqual(self.owner_only_space.description, new_description)

    def test_swd_05_collaborator_ne_moze_da_menja_space(self):
        """Saradnik ne vidi kontrolu za izmenu prostora i ne može POST zahtevom da promeni prostor."""
        self.login(self.browser, self.collaborator.email, self.password)
        self.open_space(self.browser, self.shared_space)

        self.assertFalse(
            self.browser.find_elements(By.XPATH, "//a[contains(., 'Edit Space')]")
        )

        self.open_path(
            self.browser,
            f"{reverse('app:space_detail', args=[self.shared_space.space_id])}?dialog=space-settings",
        )
        wait = self.make_wait(self.browser)
        name_input = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "form[action='/spaces/update/'] input[name='name']"))
        )
        name_input.clear()
        name_input.send_keys(f"Collaborator Change {self.unique_suffix}")
        self.browser.find_element(
            By.CSS_SELECTOR, "form[action='/spaces/update/'] button[type='submit']"
        ).click()

        self.shared_space.refresh_from_db()
        self.assertEqual(self.shared_space.name, f"Shared Space {self.unique_suffix}")
        self.assertEqual(self.shared_space.description, "Initial shared description")

    def test_swd_06_collaborator_dodaje_tekstualni_item(self):
        """Saradnik može da doda tekstualnu stavku u zajednički prostor i ona ostaje vidljiva nakon reload-a."""
        self.login(self.browser, self.collaborator.email, self.password)
        item_text = f"Collaborator item {self.unique_suffix}"

        self.create_text_item(self.browser, self.shared_space, item_text)

        self.browser.refresh()
        self.wait_for_item_card(self.browser, item_text)
        self.assertTrue(
            Item.objects.filter(space=self.shared_space, added_by=self.collaborator, content_text=item_text).exists()
        )

    def test_swd_07_viewer_ne_moze_da_doda_item(self):
        """Posmatrač ne vidi Add Item kontrolu i ne može da sačuva tekstualnu stavku direktnom web akcijom."""
        now = timezone.now()
        Membership.objects.create(
            space=self.shared_space,
            user=self.viewer,
            joined_via=self.share_link,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.login(self.browser, self.viewer.email, self.password)
        self.open_space(self.browser, self.shared_space)

        self.assertFalse(self.browser.find_elements(By.XPATH, "//a[contains(., 'Add Item')]"))

        blocked_text = f"Viewer blocked item {self.unique_suffix}"
        self.open_path(
            self.browser,
            f"{reverse('app:space_detail', args=[self.shared_space.space_id])}?dialog=add-item",
        )
        wait = self.make_wait(self.browser)
        field = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "form[data-item-form] textarea[data-item-capture-field]"))
        )
        field.send_keys(blocked_text)
        self.browser.find_element(By.CSS_SELECTOR, "form[data-item-form] button[type='submit']").click()

        self.assertFalse(Item.objects.filter(space=self.shared_space, content_text=blocked_text).exists())
        self.assertFalse(self.browser.find_elements(By.XPATH, f"//article[contains(@class, 'item-card')][@data-content={self.xpath_literal(blocked_text)}]"))

    def test_swd_08_viewer_salje_zahtev_owner_ga_odobrava(self):
        """Viewer šalje zahtev za collaborator pristup, owner ga odobrava, a članstvo i status zahteva se ažuriraju."""
        owner_browser = self.spawn_browser()
        viewer_browser = self.spawn_browser()

        self.login(viewer_browser, self.viewer.email, self.password)
        self.open_path(viewer_browser, self.share_access_url)
        self.make_wait(viewer_browser).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Join as Viewer']"))
        ).click()
        self.wait_for_text(viewer_browser, By.TAG_NAME, "body", self.shared_space.name)

        self.open_team_modal(viewer_browser, self.shared_space)
        self.make_wait(viewer_browser).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Request collaborator access']"))
        ).click()
        self.wait_for_text(viewer_browser, By.TAG_NAME, "body", "Collaborator request sent.")

        self.login(owner_browser, self.owner.email, self.password)
        self.open_team_modal(owner_browser, self.shared_space)
        self.wait_for_text(owner_browser, By.TAG_NAME, "body", self.viewer.full_name)
        owner_browser.find_element(By.XPATH, "//a[normalize-space()='Accept']").click()
        self.make_wait(owner_browser).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "form[action='/requests/review/']"))
        )
        owner_browser.find_element(
            By.CSS_SELECTOR, "form[action='/requests/review/'] button[type='submit']"
        ).click()
        self.wait_for_text(owner_browser, By.TAG_NAME, "body", "is now a collaborator.")

        viewer_browser.refresh()
        self.wait_for_text(viewer_browser, By.TAG_NAME, "body", self.shared_space.name)
        self.assertTrue(viewer_browser.find_elements(By.XPATH, "//a[contains(., 'Add Item')]"))

        request_record = CollaborationRequest.objects.get(space=self.shared_space, requester=self.viewer)
        membership = Membership.objects.get(space=self.shared_space, user=self.viewer)
        self.assertEqual(request_record.status, CollaborationRequest.Status.APPROVED)
        self.assertEqual(membership.role, Membership.Role.COLLABORATOR)
        self.assertEqual(membership.status, Membership.Status.ACTIVE)

    def test_swd_09_item_drugog_korisnika_pojavljuje_se_bez_rucnog_reload_a(self):
        """Tekstualna stavka dodatа od strane saradnika pojavljuje se kod owner-a bez ručnog osvežavanja stranice."""
        self.require_realtime_socket_support()

    def test_swd_10_realtime_mehanizam_ne_dodaje_duplikate(self):
        """Automatsko osvežavanje prikazuje novu stavku samo jednom i ne duplira karticu u istom prostoru."""
        self.require_realtime_socket_support()
