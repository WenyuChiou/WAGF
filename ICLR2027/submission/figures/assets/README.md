# Figure 1 generated assets

`figure1_architecture_reset_D_final_v3.png` is the reviewed generated
agent-paper composition used by the active ICLR manuscript. It contains the
LLM cue, functional icons, borders, fills, arrows, labels, and background as
one generated raster image. Its architecture places Validator between the
action and Environment, and routes the shared condition directly to Filter.

Other files in this directory are generation intermediates or historical style
references. They are not active manuscript figures. Run
`source/figure1_overlay.py` to stage the reviewed asset into `figures/active/`.
