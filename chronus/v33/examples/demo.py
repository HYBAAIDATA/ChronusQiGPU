from chronus.v33 import ChronosEngine

engine = ChronosEngine()
result = engine.render("sunset sphere glass")
print("Energy:", result.energy)
print("Frame shape:", result.frame_shape)
print("Raster compression ratio:", result.raster_compression_ratio)
print(f"Rendered pixels: {result.rendered_pixels_hit} / {result.total_pixels}")
