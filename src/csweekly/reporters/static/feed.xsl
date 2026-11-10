<?xml version="1.0" encoding="utf-8"?>
<!-- Optional browser-friendly view of the Atom feed. Readers ignore this. -->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <xsl:output method="html" encoding="utf-8" indent="yes"/>
  <xsl:template match="/">
    <html lang="en">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title><xsl:value-of select="atom:feed/atom:title"/> — Atom feed</title>
        <style>
          :root { color-scheme: light dark; }
          body {
            font-family: "IBM Plex Sans", system-ui, sans-serif;
            max-width: 42rem;
            margin: 2rem auto;
            padding: 0 1rem;
            line-height: 1.5;
          }
          h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
          .lede { color: #666; margin-top: 0; }
          .note {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            margin: 1.25rem 0;
            background: rgba(127,127,127,0.08);
          }
          article {
            border-top: 1px solid #ccc;
            padding: 1rem 0;
          }
          pre {
            white-space: pre-wrap;
            font-family: "IBM Plex Mono", ui-monospace, monospace;
            font-size: 0.9rem;
          }
          a { color: inherit; }
        </style>
      </head>
      <body>
        <h1><xsl:value-of select="atom:feed/atom:title"/></h1>
        <p class="lede"><xsl:value-of select="atom:feed/atom:subtitle"/></p>
        <div class="note">
          <strong>This is an Atom feed.</strong>
          Browsers may show this friendly page via XSL, or raw XML.
          To subscribe, copy the feed URL into Feedly, Inoreader, NetNewsWire,
          Thunderbird, or another reader — see
          <a href="subscribe.html">subscribe.html</a>.
        </div>
        <xsl:for-each select="atom:feed/atom:entry">
          <article>
            <h2>
              <a>
                <xsl:attribute name="href"><xsl:value-of select="atom:link/@href"/></xsl:attribute>
                <xsl:value-of select="atom:title"/>
              </a>
            </h2>
            <p class="lede">Updated <xsl:value-of select="atom:updated"/></p>
            <pre><xsl:value-of select="atom:summary"/></pre>
          </article>
        </xsl:for-each>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
