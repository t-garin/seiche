#let report(
  experiment: "",
  metadata: (:),
  sections: (:),
) = {
  set page(paper: "a4", margin: 2.5cm)
  set text(size: 10.5pt)

  align(center)[
    #text(size: 26pt, weight: "bold", fill: rgb("#1a5276"))[SEICHE Report]
    #v(6pt)
    #text(size: 16pt)[#experiment]
  ]
  v(16pt)

  heading(level: 1, numbering: none)[Configuration]
  table(
    columns: (auto, 1fr),
    ..metadata.flatten(),
  )

  for (name, plots) in sections {
    if plots.len() > 0 {
      pagebreak(weak: true)
      heading(level: 1, numbering: none)[#name]
      grid(
        columns: (1fr, 1fr),
        gutter: 1em,
        ..plots.map(
          plot => figure(image(plot.path, width: 100%), caption: [#plot.caption]),
        ),
      )
    }
  }
}
