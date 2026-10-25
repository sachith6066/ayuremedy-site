# AyuRemedy website

Static site for AyuRemedy Ayurveda Clinic, Treatment Centre & Pharmacy, Ramamurthy Nagar, Bengaluru (www.ayuremedy.com).

## Edit and build

- Page content: `src/pages/*.html` (each starts with a small title/description/path header)
- Shared header and footer: `src/layout.html`
- Styles and scripts: `assets/css/site.css`, `assets/js/site.js`
- Clinic hours, address and doctors for Google: the `CLINIC` block in `build.py`

```
python3 build.py
```

writes the finished site to `public/`.

## Publishing

The site is hosted on GitHub Pages. Every push to `main` runs `.github/workflows/deploy.yml`,
which builds the site and publishes `public/` to https://www.ayuremedy.com.

Every page keeps its old WordPress address (`/about-us/`, `/panchakarma-treatments/` and so on),
and images and videos stay at their old `/wp-content/uploads/` paths, so search rankings and old links carry over.

## Email

Email is NOT on GitHub. The mailboxes stay on the old HostGator India / BigRock hosting (103.53.42.63).
DNS at GoDaddy points `mail`, `webmail`, `cpanel` and the MX record there. See `docs/dns-before-golive.txt`
for the original records and how to roll back.
