from __future__ import annotations

from .models import ChapterLink, Volume

VOLUME_URL_OVERRIDES: dict[int, tuple[str, ...]] = {
	1: (
		"https://wanderinginn.com/2017/03/03/rw1-00/",
		"https://wanderinginn.com/2017/03/03/rw1-01/",
		"https://wanderinginn.com/2017/03/03/rw1-02/",
		"https://wanderinginn.com/2017/03/03/rw1-03/",
		"https://wanderinginn.com/2017/03/03/rw1-04/",
		"https://wanderinginn.com/2017/03/03/rw1-05/",
		"https://wanderinginn.com/2017/03/03/rw1-06/",
		"https://wanderinginn.com/2017/03/03/rw1-07/",
		"https://wanderinginn.com/2017/03/03/rw1-08/",
		"https://wanderinginn.com/2017/03/03/rw1-09/",
		"https://wanderinginn.com/2017/03/03/rw1-10/",
		"https://wanderinginn.com/2017/03/03/rwinterlude-the-great-ritual/",
		"https://wanderinginn.com/2017/03/03/rw1-11/",
		"https://wanderinginn.com/2017/03/03/rw1-12/",
		"https://wanderinginn.com/2017/03/03/rw1-13/",
		"https://wanderinginn.com/2017/03/03/rw1-14/",
		"https://wanderinginn.com/2017/03/03/rw1-15/",
		"https://wanderinginn.com/2017/03/03/rw1-16/",
		"https://wanderinginn.com/2017/03/03/rw1-17/",
		"https://wanderinginn.com/2017/03/03/rw1-18/",
		"https://wanderinginn.com/2017/03/03/rw1-19-r/",
		"https://wanderinginn.com/2017/03/03/rw1-20-r/",
		"https://wanderinginn.com/2017/03/03/rw1-21/",
		"https://wanderinginn.com/2017/03/03/rw1-22/",
		"https://wanderinginn.com/2017/03/03/rw1-23-a/",
		"https://wanderinginn.com/2017/03/04/rw1-24/",
		"https://wanderinginn.com/2017/03/04/rwinterlude-king-edition/",
		"https://wanderinginn.com/2017/03/04/rw1-25/",
		"https://wanderinginn.com/2017/03/04/rw1-26-r/",
		"https://wanderinginn.com/2017/03/04/rw1-27-r/",
		"https://wanderinginn.com/2017/03/04/rw1-28-a/",
		"https://wanderinginn.com/2017/03/04/rw1-29/",
		"https://wanderinginn.com/2017/03/04/rw1-30/",
		"https://wanderinginn.com/2017/03/04/rw1-31/",
		"https://wanderinginn.com/2017/03/04/rw1-32-r/",
		"https://wanderinginn.com/2017/03/04/rw1-33-r/",
		"https://wanderinginn.com/2017/03/04/rw1-34/",
		"https://wanderinginn.com/2017/03/04/rw1-35-r/",
		"https://wanderinginn.com/2017/03/04/rw1-36/",
		"https://wanderinginn.com/2017/03/04/rw1-37/",
		"https://wanderinginn.com/2017/03/04/rw1-38/",
		"https://wanderinginn.com/2017/03/04/rw1-39-r/",
		"https://wanderinginn.com/2017/03/04/rw1-40-r/",
		"https://wanderinginn.com/2017/03/04/rw1-41/",
		"https://wanderinginn.com/2017/03/04/rw1-42/",
		"https://wanderinginn.com/2017/03/04/rw1-43-r/",
		"https://wanderinginn.com/2017/03/04/rw1-44-r/",
		"https://wanderinginn.com/2017/03/04/rw1-45/",
		"https://wanderinginn.com/2017/03/04/rw1-46/",
		"https://wanderinginn.com/2017/03/04/rw1-47-r/",
		"https://wanderinginn.com/2017/03/04/rw1-48-r/",
		"https://wanderinginn.com/2017/03/04/rw1-49/",
		"https://wanderinginn.com/2017/03/04/rw1-50/",
		"https://wanderinginn.com/2017/03/04/rw1-51/",
		"https://wanderinginn.com/2017/03/04/rw1-52-r/",
		"https://wanderinginn.com/2017/03/04/rw1-53/",
		"https://wanderinginn.com/2017/03/04/rw1-54/",
		"https://wanderinginn.com/2017/03/04/rw1-55-r/",
		"https://wanderinginn.com/2017/03/04/rw1-56/",
		"https://wanderinginn.com/2017/03/04/rw1-57-h/",
		"https://wanderinginn.com/2017/03/04/rw1-58-h/",
		"https://wanderinginn.com/2017/03/04/rw1-59-h/",
		"https://wanderinginn.com/2017/03/04/rw1-60/",
		"https://wanderinginn.com/2017/03/04/rw1-61/",
		"https://wanderinginn.com/2017/03/04/rw1-62/",
		"https://wanderinginn.com/2017/03/04/rw1-63/",
	),
	2: (
		"https://wanderinginn.com/2017/03/07/interlude-2/",
		"https://wanderinginn.com/2017/03/12/2-01/",
		"https://wanderinginn.com/2017/03/15/2-02/",
		"https://wanderinginn.com/2017/03/18/2-03/",
		"https://wanderinginn.com/2017/03/22/2-04/",
		"https://wanderinginn.com/2017/03/25/2-05/",
		"https://wanderinginn.com/2017/03/28/2-06/",
		"https://wanderinginn.com/2017/04/02/2-06-2/",
		"https://wanderinginn.com/2017/04/02/2-07/",
		"https://wanderinginn.com/2017/04/04/2-08/",
		"https://wanderinginn.com/2017/04/09/2-09/",
		"https://wanderinginn.com/2017/04/12/2-10/",
		"https://wanderinginn.com/2017/04/12/2-00-t/",
		"https://wanderinginn.com/2017/04/13/2-11/",
		"https://wanderinginn.com/2017/04/14/2-12/",
		"https://wanderinginn.com/2017/04/15/2-13/",
		"https://wanderinginn.com/2017/04/16/2-00-g/",
		"https://wanderinginn.com/2017/04/17/side-story-mating-rituals/",
		"https://wanderinginn.com/2017/04/18/2-14/",
		"https://wanderinginn.com/2017/04/22/2-15/",
		"https://wanderinginn.com/2017/04/22/2-16/",
		"https://wanderinginn.com/2017/04/25/2-17/",
		"https://wanderinginn.com/2017/04/27/2-01-g/",
		"https://wanderinginn.com/2017/04/29/2-18/",
		"https://wanderinginn.com/2017/05/03/2-19/",
		"https://wanderinginn.com/2017/05/05/2-00-k/",
		"https://wanderinginn.com/2017/05/07/2-20/",
		"https://wanderinginn.com/2017/05/10/2-01-t/",
		"https://wanderinginn.com/2017/05/14/2-21/",
		"https://wanderinginn.com/2017/05/17/2-22/",
		"https://wanderinginn.com/2017/05/18/1-00-c/",
		"https://wanderinginn.com/2017/05/19/1-01-c/",
		"https://wanderinginn.com/2017/05/21/2-02-g/",
		"https://wanderinginn.com/2017/05/24/2-23/",
		"https://wanderinginn.com/2017/05/26/2-24/",
		"https://wanderinginn.com/2017/05/28/2-25/",
		"https://wanderinginn.com/2017/05/31/2-26/",
		"https://wanderinginn.com/2017/06/04/2-00-h/",
		"https://wanderinginn.com/2017/06/07/2-27/",
		"https://wanderinginn.com/2017/06/09/2-28/",
		"https://wanderinginn.com/2017/06/11/2-29/",
		"https://wanderinginn.com/2017/06/14/2-03-g/",
		"https://wanderinginn.com/2017/06/18/2-30/",
		"https://wanderinginn.com/2017/06/21/2-31/",
		"https://wanderinginn.com/2017/06/24/interlude-3/",
		"https://wanderinginn.com/2017/06/25/s02-the-antinium-wars-pt-1/",
		"https://wanderinginn.com/2017/06/26/s02-the-antinium-wars-pt-2/",
		"https://wanderinginn.com/2017/06/27/2-32/",
		"https://wanderinginn.com/2017/07/01/2-33/",
		"https://wanderinginn.com/2017/07/04/2-34/",
		"https://wanderinginn.com/2017/07/08/2-35/",
		"https://wanderinginn.com/2017/07/11/2-36/",
		"https://wanderinginn.com/2017/07/15/2-37/",
		"https://wanderinginn.com/2017/07/18/2-38/",
		"https://wanderinginn.com/2017/07/22/2-39/",
		"https://wanderinginn.com/2017/07/25/2-40/",
		"https://wanderinginn.com/2017/07/29/2-41/",
	),
}


def apply_volume_overrides(volumes: dict[int, Volume]) -> dict[int, Volume]:
	updated = dict(volumes)
	for number, urls in VOLUME_URL_OVERRIDES.items():
		existing = volumes.get(number)
		titles_by_url = (
			{chapter.url.rstrip("/"): chapter.title for chapter in existing.chapters}
			if existing
			else {}
		)
		chapters = tuple(
			ChapterLink(
				title=titles_by_url.get(url.rstrip("/"), _title_from_url(url)),
				url=url,
			)
			for url in urls
		)
		updated[number] = Volume(
			number=number,
			title=existing.title if existing else f"Volume {number}",
			chapters=chapters,
		)
	return updated


def _title_from_url(url: str) -> str:
	slug = url.rstrip("/").rsplit("/", 1)[-1]
	return slug.replace("-", " ").title()
