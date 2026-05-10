"""Seed initial rows: dev user, sources, entities.

Idempotent — safe to re-run. Values mirror the frontend's lib/mock-data.ts
so before-and-after the seed, the UI looks the same.

Usage:
    python -m scripts.seed
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models import Entity, Source, User
from app.models.base import EntityKind, Lang, SourceKind, SourceTier

configure_logging()
log = get_logger("seed")
settings = get_settings()


SOURCES: list[dict] = [
    # free RSS — these actually work end-to-end with the RSSFetcher
    dict(slug="bbc", name="BBC News", lang=Lang.en, region="UK", kind=SourceKind.rss,
         tier=SourceTier.free, fetcher="rss", needs_cookies=False, enabled=True,
         feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
         schedule_cron="*/10 * * * *"),
    dict(slug="reuters-world", name="Reuters World", lang=Lang.en, region="US", kind=SourceKind.rss,
         tier=SourceTier.free, fetcher="rss", needs_cookies=False, enabled=True,
         feed_url="https://feeds.reuters.com/reuters/worldNews",
         schedule_cron="*/10 * * * *"),
    dict(slug="nhk", name="NHK News", name_local="NHKニュース", lang=Lang.ja, region="JP",
         kind=SourceKind.rss, tier=SourceTier.free, fetcher="rss", needs_cookies=False,
         enabled=True, feed_url="https://www3.nhk.or.jp/rss/news/cat0.xml",
         schedule_cron="*/10 * * * *"),
    dict(slug="asahi", name="Asahi Shimbun", name_local="朝日新聞", lang=Lang.ja, region="JP",
         kind=SourceKind.rss, tier=SourceTier.free, fetcher="rss", needs_cookies=False,
         enabled=True, feed_url="https://www.asahi.com/rss/asahi/newsheadlines.rdf",
         schedule_cron="*/15 * * * *"),
    # paywall stubs — configured but fetcher not yet implemented; the UI shows them
    dict(slug="nikkei", name="Nikkei", name_local="日本経済新聞", lang=Lang.ja, region="JP",
         kind=SourceKind.html, tier=SourceTier.paywall, fetcher="nikkei",
         needs_cookies=True, enabled=False, schedule_cron="*/15 * * * *"),
    dict(slug="caixin", name="Caixin", name_local="财新", lang=Lang.zh, region="CN",
         kind=SourceKind.html, tier=SourceTier.paywall, fetcher="caixin",
         needs_cookies=True, enabled=False, schedule_cron="*/20 * * * *"),
    dict(slug="scmp", name="South China Morning Post", lang=Lang.en, region="HK",
         kind=SourceKind.html, tier=SourceTier.paywall, fetcher="scmp",
         needs_cookies=True, enabled=False, schedule_cron="*/15 * * * *"),
    dict(slug="economist", name="The Economist", lang=Lang.en, region="UK",
         kind=SourceKind.html, tier=SourceTier.paywall, fetcher="economist",
         needs_cookies=True, enabled=False, schedule_cron="0 */2 * * *"),
    dict(slug="ft", name="Financial Times", lang=Lang.en, region="UK",
         kind=SourceKind.html, tier=SourceTier.paywall, fetcher="ft",
         needs_cookies=True, enabled=False, schedule_cron="*/15 * * * *"),
    dict(slug="bloomberg", name="Bloomberg", lang=Lang.en, region="US",
         kind=SourceKind.html, tier=SourceTier.paywall, fetcher="bloomberg",
         needs_cookies=True, enabled=False, schedule_cron="*/15 * * * *"),
    dict(slug="yahoo-jp", name="Yahoo! News Japan", name_local="Yahoo!ニュース",
         lang=Lang.ja, region="JP", kind=SourceKind.rss, tier=SourceTier.free,
         fetcher="rss", needs_cookies=False, enabled=False,
         feed_url="https://news.yahoo.co.jp/rss/topics/top-picks.xml",
         schedule_cron="*/10 * * * *"),
]


ENTITIES: list[dict] = [
    dict(slug="elon-musk", canonical_name="Elon Musk", name_local="马斯克",
         kind=EntityKind.person, wikidata_qid="Q317521",
         aliases=["Elon Musk", "马斯克", "イーロン・マスク", "Elon", "@elonmusk"],
         description="CEO of Tesla and SpaceX; owner of X Corp."),
    dict(slug="jensen-huang", canonical_name="Jensen Huang", name_local="黄仁勋",
         kind=EntityKind.person, wikidata_qid="Q1282014",
         aliases=["Jensen Huang", "黄仁勋", "黃仁勳", "ジェンスン・フアン"],
         description="Founder and CEO of Nvidia Corporation."),
    dict(slug="donald-trump", canonical_name="Donald Trump", name_local="特朗普",
         kind=EntityKind.person, wikidata_qid="Q22686",
         aliases=["Donald Trump", "特朗普", "トランプ", "Trump"],
         description="US political figure."),
    dict(slug="sam-altman", canonical_name="Sam Altman", kind=EntityKind.person,
         wikidata_qid="Q6126221",
         aliases=["Sam Altman", "サム・アルトマン", "奥特曼"],
         description="CEO of OpenAI."),
    dict(slug="jerome-powell", canonical_name="Jerome Powell", kind=EntityKind.person,
         wikidata_qid="Q622401",
         aliases=["Jerome Powell", "Jay Powell", "パウエル", "鲍威尔"],
         description="Chair of the US Federal Reserve."),
    dict(slug="kazuo-ueda", canonical_name="Kazuo Ueda", name_local="植田和男",
         kind=EntityKind.person, wikidata_qid="Q11414001",
         aliases=["Kazuo Ueda", "植田和男", "植田総裁"],
         description="Governor of the Bank of Japan."),
    dict(slug="nvidia", canonical_name="Nvidia", kind=EntityKind.company,
         wikidata_qid="Q182477",
         aliases=["Nvidia", "NVDA", "エヌビディア", "英伟达"],
         description="Semiconductor company specialising in GPUs and AI accelerators."),
    dict(slug="tesla", canonical_name="Tesla", kind=EntityKind.company,
         wikidata_qid="Q478214",
         aliases=["Tesla", "TSLA", "テスラ", "特斯拉"],
         description="Electric-vehicle and energy-storage manufacturer."),
    dict(slug="openai", canonical_name="OpenAI", kind=EntityKind.company,
         wikidata_qid="Q21708200",
         aliases=["OpenAI", "オープンAI"],
         description="AI research and deployment company."),
    dict(slug="tsmc", canonical_name="TSMC", kind=EntityKind.company,
         wikidata_qid="Q188920",
         aliases=["TSMC", "Taiwan Semiconductor", "台積電", "台积电"],
         description="Taiwan Semiconductor Manufacturing Company."),
    dict(slug="apple", canonical_name="Apple", kind=EntityKind.company,
         wikidata_qid="Q312",
         aliases=["Apple", "AAPL", "苹果", "アップル"],
         description="Consumer-electronics and software company."),
    dict(slug="boj", canonical_name="Bank of Japan", name_local="日本銀行",
         kind=EntityKind.company, wikidata_qid="Q211003",
         aliases=["Bank of Japan", "BOJ", "日本銀行", "日银"],
         description="Japan's central bank."),
]


async def seed() -> None:
    engine = create_async_engine(settings.db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # dev user
        existing = await db.execute(select(User).where(User.id == settings.dev_user_id))
        if existing.scalar_one_or_none() is None:
            db.add(User(id=settings.dev_user_id, email=settings.dev_user_email))
            log.info("seed.user", email=settings.dev_user_email)

        # sources
        for row in SOURCES:
            stmt = pg_insert(Source).values(**row).on_conflict_do_update(
                index_elements=["slug"],
                set_={k: row[k] for k in row if k != "slug"},
            )
            await db.execute(stmt)
        log.info("seed.sources", count=len(SOURCES))

        # entities
        for row in ENTITIES:
            stmt = pg_insert(Entity).values(**row).on_conflict_do_update(
                index_elements=["slug"],
                set_={k: row[k] for k in row if k != "slug"},
            )
            await db.execute(stmt)
        log.info("seed.entities", count=len(ENTITIES))

        await db.commit()

    await engine.dispose()
    log.info("seed.done")


if __name__ == "__main__":
    asyncio.run(seed())
