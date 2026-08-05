# Figure 1 generated assets

`figure1_architecture_compact_v1.png` is the reviewed generated agent-paper
composition used by the active ICLR manuscript. It contains the LLM cue,
functional icons, borders, fills, arrows, labels, and background as one
generated raster image. Its local semantic nodes separate runtime from
measurement without full-canvas lane frames; the Agent boundary owns the
response, the accepted-decision arrow lands on the aligned Decision log, and
the shared condition routes directly to Filter.

Other files in this directory are generation intermediates or historical style
references. They are not active manuscript figures. Run
`source/figure1_overlay.py` to stage the reviewed asset into `figures/active/`.
