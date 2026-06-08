import requests
from bs4 import BeautifulSoup
from stacktwin.pipeline.sources.base import BaseSource, Article


GITHUB_TRENDING_URL = "https://github.com/trending/{language}?since=weekly"

DEFAULT_LANGUAGES = [
    "",
    "python",
    "typescript",
    "csharp",
]


class GitHubTrendingSource(BaseSource):

    def __init__(self, languages: list[str] | None = None):
        self.languages = languages or DEFAULT_LANGUAGES
        self._status = "ready"

    @property
    def name(self) -> str:
        return "GitHub Trending"

    @property
    def source_type(self) -> str:
        return "github_trending"

    @property
    def status(self) -> str:
        return self._status

    def fetch(self, limit: int = 50) -> list[Article]:
        articles = []
        seen_urls = set()
        per_language = max(1, limit // len(self.languages))

        for language in self.languages:
            try:
                url = GITHUB_TRENDING_URL.format(language=language)
                response = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                repos = soup.select("article.Box-row")

                count = 0
                for repo in repos:
                    if count >= per_language:
                        break

                    h2 = repo.select_one("h2 a")
                    if not h2:
                        continue

                    path = h2.get("href", "").strip()
                    repo_url = f"https://github.com{path}"

                    if repo_url in seen_urls:
                        continue
                    seen_urls.add(repo_url)

                    parts = path.strip("/").split("/")
                    repo_name = "/".join(parts) if len(parts) >= 2 else path

                    desc_el = repo.select_one("p")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    lang_el = repo.select_one("[itemprop='programmingLanguage']")
                    lang_tag = lang_el.get_text(strip=True) if lang_el else language

                    star_el = repo.select_one("a[href$='/stargazers']")
                    stars_text = star_el.get_text(strip=True).replace(",", "") if star_el else "0"
                    try:
                        stars = int(stars_text)
                    except ValueError:
                        stars = 0

                    articles.append(Article(
                        title=repo_name,
                        url=repo_url,
                        source=self.source_type,
                        summary=description,
                        tags=[lang_tag] if lang_tag else [],
                        published_at="",
                        score=stars
                    ))
                    count += 1

            except Exception as e:
                print(f"[GitHubTrending] failed for language '{language}': {e}")
                self._status = f"degraded:error={e}"
                continue

        self._status = f"ok:{len(articles)}_articles"
        return articles[:limit]