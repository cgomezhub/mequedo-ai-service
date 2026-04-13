from crewai_tools import ScrapeWebsiteTool


def get_faq_scraper() -> ScrapeWebsiteTool:
    """
    Returns an instantiated ScrapeWebsiteTool statically pointed at Mequedo's FAQ domain.
    """
    return ScrapeWebsiteTool(
        website_url="https://www.mequedo.app/faq"
    )
