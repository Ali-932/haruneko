import { Tags } from '../Tags';
import icon from './MangaHere.webp';
import { FetchWindowScript } from '../platform/FetchProvider';
import { DecoratableMangaScraper, type Manga, Chapter } from '../providers/MangaPlugin';
import * as Common from './decorators/Common';
import * as DM5 from './decorators/DM5';

@Common.MangaCSS(/^{origin}\/manga\/[^/]+\/$/, 'div.detail-info span.detail-info-right-title-font')
@Common.MangasSinglePageCSS('/mangalist/', 'div.browse-new-block-list div.browse-new-block p.browse-new-block-content a', Common.AnchorInfoExtractor(true))
@DM5.PagesSinglePageScript()
@Common.ImageAjax()
export default class extends DecoratableMangaScraper /* MangaFox */ {

    public constructor() {
        super('mangahere', 'MangaHere', 'https://www.mangahere.cc', Tags.Media.Manga, Tags.Media.Manhwa, Tags.Media.Manhua, Tags.Language.English, Tags.Source.Aggregator);
    }

    public override async Initialize(): Promise<void> {
        const request = new Request(this.URI.href);
        return FetchWindowScript(request, `document.cookie = 'isAdult=1; path=/; max-age=31536000'`);
    }

    public override async FetchChapters(manga: Manga): Promise<Chapter[]> {
        // Must use FetchWindowScript instead of FetchCSS to ensure cookies are set
        // because FetchCSS uses standard fetch which doesn't have access to Puppeteer cookies
        const uri = new URL(manga.Identifier, this.URI);
        const request = new Request(uri.href);

        const data = await FetchWindowScript<{ id: string, title: string }[]>(request, `
            // Set the cookie to ensure 18+ content is accessible
            document.cookie = 'isAdult=1; path=/; max-age=31536000';

            // Extract chapters
            return [...document.querySelectorAll('div#chapterlist ul li a')].map(a => ({
                id: new URL(a.href).pathname,
                title: a.textContent.trim()
            }));
        `);

        return data.map(({ id, title }) => {
            const cleanTitle = title.replace(manga.Title, '').trim() || manga.Title;
            return new Chapter(this, manga, id, cleanTitle);
        });
    }

    public override get Icon() {
        return icon;
    }
}