// The Morning Current: page parts and styles for the layout engine (Typst).
// mc/style.py prepends `#let P = (...)` with the paper profile's geometry and type scale; the templates in
// mc/templates.py call these functions. Every story column region and its blocks carry invisible markers
// (`mk`) so mc/measure.py can read back where each block landed and how full each column is.

#let ink = rgb(P.ink)
#let C(name) = rgb(P.at(name))
#let SERIF = ("MC Serif", "MC Serif Ext", "Libertinus Serif")
#let HEAD = ("MC Playfair", "MC Playfair Ext", "MC Serif")
#let SANS = ("MC Franklin", "MC Franklin Ext", "MC Serif")
#let FRAKTUR = ("MC Fraktur", "MC Playfair")
#let T = P.T
#let Z = P.Z

// lines are exactly 1em tall, so `leading` = (line-height - 1)em like CSS line-height
#let lh(x) = (x - 1) * 1em
#let sans(size, weight: 400, track: 0em, body) = text(font: SANS, size: size, weight: weight, tracking: track, number-type: "lining", body)
#let caps(size, weight: 800, track: 0.12em, body) = sans(size, weight: weight, track: track, upper(body))

#set document(title: P.title)
#set text(font: SERIF, size: P.body * 1pt, lang: "en", hyphenate: true, number-type: "old-style", fill: ink,
          top-edge: 0.8em, bottom-edge: -0.2em, costs: (widow: 200%, orphan: 200%))
#set par(justify: true, leading: lh(P.leading), spacing: 0pt, first-line-indent: (amount: 1.1em, all: true),
         linebreaks: "optimized")
#set block(spacing: 0pt)
#set table(inset: 0pt, stroke: none)
#set grid(gutter: 0pt)
#show strong: set text(weight: 700)

// ------------------------------------------------------------------ measuring
#let mk(id) = context [#metadata((id: id, pg: here().page(), x: here().position().x.pt(), y: here().position().y.pt()))<mk>]
#let region-mark(slot, n) = layout(size => mk("rs|" + slot + "|" + str(n) + "|" + str(size.width.pt())))

#let fit-width(body) = layout(size => context {
  let w = measure(body).width
  if w > size.width { scale(x: size.width / w * 100%, y: size.width / w * 100%, reflow: true, body) } else { body }
})
// ------------------------------------------------------------------ pages
#let page-frame(n, front: false, section: "", lhead: "", rhead: "", body) = {
  let recto = calc.odd(n)
  let (ml, mr) = if recto { (P.m-inner, P.m-outer) } else { (P.m-outer, P.m-inner) }
  let mtop = if front { P.m-top-front } else { P.m-top }
  let fg = if front { none } else {
    place(top + left, dx: ml * 1in, dy: P.m-rhead * 1in, block(width: P.pw * 1in - (ml + mr) * 1in,
      stroke: (bottom: 0.6pt + ink), inset: (bottom: 3pt),
      grid(columns: (auto, 1fr, auto), column-gutter: 8pt,
        caps(6.6pt, weight: 400, track: 0.14em, lhead),
        align(center, fit-width(caps(6.6pt, weight: 800, track: 0.14em, section))),
        caps(6.6pt, weight: 400, track: 0.14em, rhead))))
    place(bottom + (if recto { right } else { left }), dx: if recto { -mr * 1in } else { ml * 1in },
          dy: -P.m-folio * 1in, sans(7pt, weight: 700, str(n)))
  }
  page(width: P.pw * 1in, height: P.ph * 1in, margin: (left: ml * 1in, right: mr * 1in, top: mtop * 1in, bottom: P.m-bottom * 1in),
       foreground: fg, {
    mk("pg|" + str(n))
    block(width: 100%, height: 100%, breakable: false, {
      body
      mk("pe|" + str(n))
    })
  })
}

// ------------------------------------------------------------------ type
#let kicker(body) = block(below: 3pt, caps(T.kicker * 1pt, track: 0.18em,
  box(stroke: (bottom: 1.4pt + ink), inset: (bottom: 1pt), outset: (bottom: 0pt), body)))
#let hed(size, lead: 1.02, body) = block(text(font: HEAD, weight: 800, size: size * 1pt, tracking: -0.005em, number-type: "lining",
  par(justify: false, leading: lh(lead), first-line-indent: 0pt, body)))
#let deck(size, lead: 1.28, above: 4pt, below: 7pt, body) = block(above: above, below: below,
  text(style: "italic", size: size * 1pt, fill: C("dark"), par(justify: false, leading: lh(lead), first-line-indent: 0pt, body)))
#let headblock(kick, level, headline, dk) = block(below: 2pt, {
  kicker(kick)
  hed(T.at(level), headline)
  if dk != none { deck(T.deck, dk) } else { v(2pt) }
})
#let shead(kick, headline, dk) = block(sticky: true, below: 3pt, {
  kicker(kick)
  hed(T.h3_split, lead: 1.04, headline)
  if dk != none { deck(T.deck_split, lead: 1.26, above: 3pt, below: 4pt, dk) } else { v(3pt) }
})
#let rule(above: 6pt, below: 6pt, weight: 0.6pt) = block(above: above, below: below, line(length: 100%, stroke: weight + ink))

// ------------------------------------------------------------------ column regions
// space level 0..6 opens up a short column a little (CSS data-space)
#let SP = (p: 0.5pt, h4: 0.9pt, mini: 0.9pt)
#let region(slot, n: 2, space: 0, height: 1fr, body) = {
  block(height: height, width: 100%, breakable: false, {
    region-mark(slot, n)
    set par(spacing: space * SP.p)
    if n == 2 {
      place(top + left, dx: 50%, line(angle: 90deg, length: 100%, stroke: 0.4pt + C("rule")))
      columns(2, gutter: P.gap * 1in, body)
    } else { body }
  })
  mk("re|" + slot)
}
#let blk(slot, i, body) = { mk("s|" + slot + "|" + str(i)); body; mk("e|" + slot + "|" + str(i)) }

// ------------------------------------------------------------------ story blocks
#let para(slot, i, indent: true, body) = par(first-line-indent: if indent { (amount: 1.1em, all: true) } else { 0pt },
  { mk("s|" + slot + "|" + str(i)); body; mk("e|" + slot + "|" + str(i)) })

#let dropcap(slot, i, letter, ws) = {
  mk("s|" + slot + "|" + str(i))
  layout(size => context {
    let cap = text(font: HEAD, weight: 800, size: 34pt, top-edge: "cap-height", bottom-edge: "baseline", number-type: "lining", letter)
    let cw = measure(cap).width + 3pt
    let pitch = P.body * P.leading * 1pt
    let W = size.width - cw
    let fits(k) = measure(block(width: W, par(first-line-indent: 0pt, ws.slice(0, k).join([ ])))).height <= 3 * pitch - 0.2pt
    let (lo, hi) = (0, ws.len())
    if fits(hi) { lo = hi } else {
      while hi - lo > 1 { let mid = calc.div-euclid(lo + hi, 2); if fits(mid) { lo = mid } else { hi = mid } }
    }
    let first = ws.slice(0, lo).join([ ])
    let rest = ws.slice(lo)
    block(grid(columns: (cw, 1fr), box(inset: (top: 1.5pt), cap),
      par(first-line-indent: 0pt, if rest.len() > 0 { first + linebreak(justify: true) } else { first })))
    if rest.len() > 0 { par(first-line-indent: 0pt, rest.join([ ])) }
  })
  mk("e|" + slot + "|" + str(i))
}

#let h4(slot, i, space: 0, body) = block(sticky: true, above: 7pt + space * SP.h4, below: 2pt,
  { mk("s|" + slot + "|" + str(i)); caps(T.h4 * 1pt, track: 0.1em, body); mk("e|" + slot + "|" + str(i)) })

#let pull(slot, i, body, who) = blk(slot, i, block(breakable: false, above: 8pt, below: 8pt, width: 100%,
  stroke: (top: 1.4pt + ink, bottom: 0.6pt + ink), inset: (y: 6pt, x: 2pt),
  align(center, {
    text(font: HEAD, style: "italic", size: T.pull * 1pt, par(justify: false, leading: lh(1.2), first-line-indent: 0pt, body))
    v(4pt)
    caps(6.6pt, weight: 400, track: 0.12em, who)
  })))

#let note(slot, i, body) = blk(slot, i, block(above: 3pt, text(style: "italic", size: 7.6pt, fill: C("mid"),
  par(leading: lh(1.3), first-line-indent: 0pt, body))))

#let blist(slot, i, items) = blk(slot, i, block(above: 2pt, below: 4pt,
  list(indent: 0.3em, body-indent: 0.5em, spacing: 1.5pt, ..items.map(x => par(first-line-indent: 0pt, x)))))

#let svg(src, width: auto, height: auto) = image(bytes(src), format: "svg", width: width, height: height)

#let photo(slot, i, path, cap, credit, ratio) = blk(slot, i, block(above: 3pt, below: 6pt, breakable: false, width: 100%, {
  layout(size => {
    let h = calc.min(size.width / ratio, P.photo-max * 1in)
    image(path, width: 100%, height: h, fit: "cover")
  })
  if cap != none or credit != none {
    v(2pt)
    sans(T.src * 1pt, par(justify: false, leading: lh(1.3), first-line-indent: 0pt, {
      text(fill: C("mid"), if cap != none { cap })
      if credit != none { [ ]; text(fill: C("grey"), tracking: 0.06em, size: T.src * 0.9pt, upper(credit)) }
    }))
  }
}))

// QR + source box at the end of a story
#let srcbox(slot, i, qr, label, note, dom) = blk(slot, i, block(breakable: false, sticky: false, above: 5pt, width: 100%,
  stroke: (top: 0.6pt + ink), inset: (top: 4pt, bottom: 3pt),
  grid(columns: (auto, 1fr), column-gutter: 6pt, align: horizon, qr,
    sans(T.src * 1pt, par(justify: false, leading: lh(1.3), first-line-indent: 0pt, {
      strong(label)
      if note != none { linebreak(); note }
      linebreak()
      text(weight: 600, tracking: 0.02em, dom)
    })))))

#let cont-line(slot, i, body) = blk(slot, i, block(above: 4pt, align(right, caps(6.8pt, weight: 700, track: 0.06em, body))))

// briefs (also in, reserve)
#let also-head(slot, i, kick) = blk(slot, i, block(sticky: true, above: 9pt, { rule(above: 0pt, below: 4pt, weight: 2pt); kicker(kick) }))
#let mini(slot, i, space: 0, head, body, qr: none, credit: none) = blk(slot, i, block(breakable: false, above: space * SP.mini,
  width: 100%, stroke: (top: 0.4pt + rgb("#999")), inset: (top: 4pt, bottom: 5pt), {
  let h = caps(T.brief_head * 1pt, track: 0.06em, par(justify: false, leading: lh(1.15), first-line-indent: 0pt, head))
  if qr != none { grid(columns: (1fr, auto), column-gutter: 6pt, align: horizon, h, qr) } else { h }
  v(1.5pt)
  text(size: T.brief * 1pt, par(leading: lh(1.3), first-line-indent: 0pt, body))
  if credit != none { v(1pt); sans(T.src * 1pt, text(fill: C("mid"), par(justify: false, first-line-indent: 0pt, credit))) }
}))
// Small Wonders / roundup items
#let odd(slot, i, space: 0, head, body, qr, credit: none) = blk(slot, i, block(breakable: false, above: space * SP.mini, below: 7pt,
  width: 100%, {
  grid(columns: (1fr, auto), column-gutter: 6pt, align: horizon,
    text(font: HEAD, weight: 800, size: T.odd_head * 1pt, number-type: "lining", par(justify: false, leading: lh(1.08), first-line-indent: 0pt, head)), qr)
  v(2pt)
  par(first-line-indent: 0pt, body)
  if credit != none { v(1pt); sans(T.src * 1pt, text(fill: C("mid"), par(justify: false, first-line-indent: 0pt, credit))) }
}))

#let boxhead(body, below: 5pt, stroke: true) = block(below: below, width: 100%,
  stroke: if stroke { (bottom: 1.4pt + ink) } else { none }, inset: (bottom: 2pt), caps(7.2pt, track: 0.16em, body))
#let ibox(shade: false, inset: (x: 8pt, y: 7pt), above: 0pt, below: 0pt, body) = block(breakable: false, width: 100%,
  above: above, below: below, stroke: 0.8pt + ink, inset: inset, fill: if shade { C("shade") } else { none }, body)

#let factgrid(items, cols) = grid(columns: (1fr,) * cols, ..items.map(((big, lab)) => block(width: 100%,
  stroke: (top: 0.4pt + rgb("#999")), inset: (top: 3pt, right: 6pt, bottom: 4pt),
  text(size: 7.6pt, par(justify: false, leading: lh(1.25), first-line-indent: 0pt, {
    text(font: HEAD, weight: 900, size: 13pt, number-type: "lining", big); linebreak(); lab })))))
#let facts(slot, i, title, items, cols) = blk(slot, i, ibox(shade: true, inset: (x: 7pt, y: 5pt), above: 9pt,
  { boxhead(title, below: 3pt); factgrid(items, cols) }))

#let chart(slot, i, title, src, note) = blk(slot, i, block(breakable: false, above: 6pt, below: 7pt, width: 100%,
  stroke: (top: 1.4pt + ink), inset: (top: 4pt), {
  caps(T.chart_title * 1pt, track: 0.1em, title)
  v(3pt)
  svg(src, width: 100%)
  if note != none { v(2pt); sans(T.chart_note * 1pt, text(fill: C("mid"), par(justify: false, first-line-indent: 0pt, note))) }
}))

// ------------------------------------------------------------------ front page
#let masthead(title, d-left, d-mid, d-right, strip) = block(below: 0pt, {
  align(center, fit-width(text(font: FRAKTUR, size: T.title * 1pt, top-edge: "ascender", bottom-edge: "descender", title)))
  block(above: 4pt, width: 100%, stroke: (top: 2pt + ink, bottom: 0.6pt + ink), inset: (y: 3pt),
    grid(columns: (1fr, auto, 1fr),
      align(left, caps(6.9pt, weight: 600, track: 0.1em, d-left)),
      align(center, caps(6.9pt, weight: 600, track: 0.1em, d-mid)),
      align(right, caps(6.9pt, weight: 600, track: 0.1em, d-right))))
  if strip != none {
    block(below: 8pt, width: 100%, stroke: (bottom: 0.6pt + ink), inset: (y: 3pt),
      align(center, fit-width(caps(T.skystrip * 1pt, weight: 600, track: 0.03em, strip))))
  } else { v(8pt) }
})
#let sep = text(fill: rgb("#777"), weight: 400, [ · ])
#let index-cells(cells) = block(above: 8pt, width: 100%, stroke: (top: 2pt + ink, bottom: 0.6pt + ink),
  grid(columns: (1fr,) * Z.index_cols,
    stroke: (x, y) => if x > 0 { (left: 0.4pt + rgb("#999")) },
    inset: (x, y) => (left: if x == 0 { 0pt } else { 6pt }, right: 6pt, y: 5pt),
    ..cells.map(c => stack(spacing: 2pt, caps(6.5pt, track: 0.12em, c.at(0)),
      text(font: HEAD, weight: 700, size: 9.3pt, number-type: "lining", par(justify: false, leading: lh(1.1), first-line-indent: 0pt, c.at(1))),
      text(size: 7.8pt, par(justify: false, leading: lh(1.22), first-line-indent: 0pt, c.at(2)))))))

// ------------------------------------------------------------------ almanac
#let suntable(rows) = table(columns: (1fr, auto, auto), column-gutter: 4pt, row-gutter: 0pt,
  ..rows.map(r => (text(size: 8.6pt, r.at(0)), ..r.slice(1).map(v => align(right, sans(8.6pt, weight: 700, v))))).flatten()
  .map(c => block(inset: (y: 2pt), c)))
#let caltable(rows) = table(columns: (P.cal-day * 1in, 1fr), stroke: (x, y) => (bottom: 0.4pt + C("light")),
  ..rows.map(r => (block(inset: (top: 4pt, bottom: 3.2pt, right: 4pt), caps(7pt, track: 0.04em, r.at(0))),
                   block(inset: (y: 3.2pt), text(size: 8.6pt, par(justify: false, leading: lh(1.28), first-line-indent: 0pt, r.at(1)))))).flatten())

// ------------------------------------------------------------------ games
#let ptitle(body, size: auto) = block(below: 1pt, text(font: HEAD, weight: 900, size: if size == auto { T.ptitle * 1pt } else { size },
  number-type: "lining", body))
#let pinstr(body, above: 0pt, below: 6pt) = block(above: above, below: below, text(size: 8.5pt, style: "italic",
  par(justify: false, leading: lh(1.3), first-line-indent: 0pt, body)))
#let cell-grid(n-cols, cells, size, stroke: (x, y) => 0.6pt + ink) = table(columns: (size,) * n-cols, rows: size,
  stroke: stroke, align: center + horizon, ..cells)
#let notes-lines(n, height: auto) = block(width: 100%, height: height, clip: true,
  stack(..range(n).map(_ => block(width: 100%, height: 0.27in, stroke: (bottom: 0.5pt + rgb("#999"))))))
#let upside(body) = rotate(180deg, reflow: true, body)

// ------------------------------------------------------------------ page-specific parts
#let side-head(slot, i, kick, headline) = blk(slot, i, block(sticky: true, above: 9pt, below: 4pt, {
  rule(above: 0pt, below: 5pt, weight: 2pt); kicker(kick); hed(T.h3, headline) }))
#let split-pair(a, b) = block(height: 1fr, width: 100%, grid(columns: (1fr, 1fr), rows: (100%,),
  block(height: 100%, width: 100%, inset: (right: P.gap * 0.5in), a),
  block(height: 100%, width: 100%, inset: (left: P.gap * 0.5in), stroke: (left: 0.4pt + C("rule")), b)))
#let spread-rule() = block(below: 6pt, width: 100%, { line(length: 100%, stroke: 1pt + ink); v(1pt); line(length: 100%, stroke: 1pt + ink) })
#let small-note(body) = block(above: 4pt, text(size: 7.8pt, par(justify: false, leading: lh(1.25), first-line-indent: 0pt, body)))
#let phasetable(rows) = table(columns: (1fr, auto), column-gutter: 4pt,
  ..rows.map(r => (block(inset: (y: 2pt), text(size: 8.6pt, r.at(0))), block(inset: (y: 2pt), align(right, sans(8.6pt, weight: 700, r.at(1)))))).flatten())
#let word-box(w, pos, pron, defn) = ibox(shade: true, above: 8pt, { boxhead([Word of the Day]);
  par(first-line-indent: 0pt, { text(font: HEAD, weight: 700, size: 12pt, w); [ ]; emph([(#pos), #pron.]); [ ]; defn }) })
#let lookup-box(title, body) = ibox(above: 9pt, { boxhead(title); text(size: 8.4pt, par(leading: lh(1.3), first-line-indent: 0pt, body)) })
#let about-box(body) = ibox(shade: true, above: 9pt, below: 8pt, { boxhead([About this paper]);
  text(size: 8pt, par(justify: false, leading: lh(1.3), first-line-indent: 0pt, body)) })
#let src-row(t, o) = block(below: 2.5pt, text(size: 7.2pt, par(justify: false, leading: lh(1.32), first-line-indent: 0pt,
  hanging-indent: 1.2em, { strong(t); [ · ]; o })))

#let cryptogram(hint, ws, who) = block(breakable: false, {
  ptitle([Cryptogram]); pinstr(hint)
  sans(12.2pt, weight: 600, par(justify: false, leading: lh(2.25), first-line-indent: 0pt,
    ws.map(w => box(text(tracking: 0.16em, w))).join(h(0.75em))))
  block(above: 2pt, align(right, sans(8pt, weight: 600, [— ] + who)))
})
#let scramble(title, intro, items) = block({
  ptitle(title); pinstr(intro)
  sans(10.5pt, weight: 700, par(justify: false, leading: lh(2.1), first-line-indent: 0pt,
    items.enumerate().map(((k, w)) => [#(k + 1). #text(tracking: 0.12em, w) #box(width: 1.3in, height: 9pt, stroke: (bottom: 0.6pt + ink))]).join(linebreak())))
})
#let ladder(ws, intro, note) = block({
  ptitle([Word Ladder]); pinstr(intro)
  let n = ws.len()
  let s = Z.ladder_cell * 1in
  table(columns: (s,) * ws.at(0).len(), rows: s * 1.07, stroke: 0.6pt + ink, align: center + horizon,
    ..ws.enumerate().map(((k, w)) => w.clusters().map(ch => sans(12pt, weight: 700, if k == 0 or k == n - 1 { ch } else { [] }))).flatten())
  pinstr(above: 5pt, below: 0pt, note)
})
#let sudoku-grid(size, cells) = table(columns: (size,) * 9, rows: size, align: center + horizon,
  stroke: (x, y) => (
    left: if calc.rem(x, 3) == 0 { 2pt + ink } else { 0.5pt + rgb("#777") },
    top: if calc.rem(y, 3) == 0 { 2pt + ink } else { 0.5pt + rgb("#777") },
    right: if x == 8 { 2pt + ink } else { none }, bottom: if y == 8 { 2pt + ink } else { none }), ..cells)
#let teasers(sub, items) = block({
  ptitle(size: 13pt, [Two-Minute Teasers ] + box(baseline: -1pt, caps(7pt, weight: 700, track: 0.12em, sub)))
  v(3pt)
  grid(columns: (1fr,) * Z.teaser_cols, column-gutter: 10pt, ..items.map(((t, qq)) =>
    text(size: 8.5pt, par(justify: false, leading: lh(1.3), first-line-indent: 0pt, { strong(t); [ ]; qq }))))
})
#let xw-grid(w, h, size, cells) = table(columns: (size,) * w, rows: size, stroke: 0.8pt + ink, align: center + horizon, ..cells)
#let clue-head(body, above: 0pt) = block(above: above, below: 2pt, sticky: true, width: 100%, stroke: (bottom: 1.2pt + ink),
  caps(7.4pt, track: 0.14em, body))
#let clue(n, body) = block(below: 1pt, par(justify: false, leading: lh(1.28), first-line-indent: 0pt, hanging-indent: 1.5em,
  box(width: 1.5em, sans(0.99em, weight: 700, n)) + body))
#let ans-head(body) = block(below: 3pt, caps(6.8pt, track: 0.12em, body))
#let ans-text(body) = text(size: 8pt, par(justify: false, leading: lh(1.28), first-line-indent: 0pt, body))
