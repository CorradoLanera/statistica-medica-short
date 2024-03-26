library("tidyverse")
library(palmerpenguins)

ggplot(
  penguins,
  aes(
    x = bill_length_mm,
    y = bill_depth_mm,
    colour = species
  )
) +
  geom_point() +
  geom_smooth()
