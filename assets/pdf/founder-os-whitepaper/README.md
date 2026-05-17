# EDL OS · Founder OS Whitepaper — source

Source HTML for `assets/EDL_Founder_OS_Whitepaper_v4.pdf`.

## Regenerate

```bash
pip install weasyprint
python3 -c "from weasyprint import HTML; HTML(filename='whitepaper.html').write_pdf('../../EDL_Founder_OS_Whitepaper_v4.pdf')"
```

Renders to A4, 11 pages.

## Design

- Brand: Electric Tangerine `#FF6B1A`, Inter font, 8pt grid.
- Print layout via `@page` rules with named pages (one per section) for running headers/footers.
- Mirrors the visual language of `assets/EDL_Product_Ladder.pdf`.
- Flexbox throughout (WeasyPrint's grid support is partial); sources page uses CSS multi-column.
- Charts and icons are inline SVG so they print at vector resolution.
