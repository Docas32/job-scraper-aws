import json
import re
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

URL = "https://www.infojobs.com.br/vagas-de-emprego-ciencia+de+dados.aspx"
OUTPUT_FILE = Path(__file__).parent / "raw_jobs.json"
LOAD_MORE_ATTEMPTS = 2


def accept_cookies(page) -> None:
    selectors = [
        "#didomi-notice-agree-button",
        "button:has-text('Aceitar')",
        "button:has-text('Agree and close')",
    ]
    for selector in selectors:
        try:
            button = page.locator(selector).first
            if button.is_visible(timeout=3000):
                button.click()
                page.wait_for_timeout(1000)
                return
        except PlaywrightTimeoutError:
            continue


def load_more_jobs(page, attempt: int) -> None:
    previous_count = page.locator(".js_vacancyLoad").count()

    load_more_selectors = [
        "button:has-text('Ver mais vagas')",
        "a:has-text('Ver mais vagas')",
        "span:has-text('Ver mais vagas')",
        "[class*='loadMore']:visible",
        "[class*='load-more']:visible",
    ]

    clicked = False
    for selector in load_more_selectors:
        try:
            button = page.locator(selector).first
            if button.is_visible(timeout=2000):
                button.scroll_into_view_if_needed()
                button.click()
                clicked = True
                break
        except PlaywrightTimeoutError:
            continue

    if not clicked:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1500)

    try:
        page.wait_for_function(
            """(args) => {
                const count = document.querySelectorAll('.js_vacancyLoad').length;
                return count > args.previousCount;
            }""",
            arg={"previousCount": previous_count},
            timeout=8000,
        )
    except PlaywrightTimeoutError:
        page.wait_for_timeout(2000)

    current_count = page.locator(".js_vacancyLoad").count()
    print(f"Tentativa {attempt}: {current_count} vagas carregadas.")


def normalize_salary(raw_salary: str | None) -> str | None:
    if not raw_salary:
        return None

    cleaned = re.sub(r"\s+", " ", raw_salary).strip()
    return cleaned or None


def extract_jobs(page) -> list[dict]:
    return page.evaluate(
        """() => {
            const cards = document.querySelectorAll('.card.js_rowCard');
            const jobs = [];

            cards.forEach((card) => {
                const container = card.querySelector('.js_vacancyLoad');
                if (!container) return;

                const titleEl = container.querySelector('.js_vacancyTitle');
                const linkEl = container.querySelector('a[href*="vaga-de-"][href*="__"]');
                const companyEl =
                    container.querySelector('.d-flex.align-items-baseline .text-body a') ||
                    container.querySelector('.d-flex.align-items-baseline .text-body');

                const locationEl = Array.from(container.children).find(
                    (el) =>
                        el.tagName === 'DIV' &&
                        el.classList.contains('mb-8') &&
                        !el.classList.contains('d-inline-flex')
                );

                const salaryEl = container.querySelector('.icon-money')?.closest('div');

                const title = titleEl?.textContent?.trim() || null;
                const company = companyEl?.textContent?.replace(/\\s+/g, ' ').trim() || null;
                const location = locationEl?.textContent?.trim() || null;

                let salary = null;
                if (salaryEl) {
                    salary = salaryEl.textContent.replace(/\\s+/g, ' ').trim() || null;
                }

                let link = linkEl?.href || container.dataset.href || null;
                if (link && link.startsWith('/')) {
                    link = `https://www.infojobs.com.br${link}`;
                }

                if (!title || !link) return;

                jobs.push({
                    titulo: title,
                    empresa: company,
                    localizacao: location,
                    salario: salary,
                    link: link,
                });
            });

            return jobs;
        }"""
    )


def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    seen_links: set[str] = set()
    unique_jobs: list[dict] = []

    for job in jobs:
        link = job.get("link")
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        unique_jobs.append(job)

    return unique_jobs


def scrape_infojobs() -> list[dict]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print(f"Acessando {URL}...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".js_vacancyLoad", timeout=30000)

        accept_cookies(page)

        for attempt in range(1, LOAD_MORE_ATTEMPTS + 1):
            load_more_jobs(page, attempt)

        raw_jobs = extract_jobs(page)

        browser.close()

    jobs = deduplicate_jobs(raw_jobs)
    for job in jobs:
        job["salario"] = normalize_salary(job.get("salario"))

    return jobs


def main() -> None:
    start = time.time()
    jobs = scrape_infojobs()

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(jobs, file, ensure_ascii=False, indent=2)

    elapsed = time.time() - start
    print(f"Extraídas {len(jobs)} vagas em {elapsed:.1f}s.")
    print(f"Dados salvos em: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
