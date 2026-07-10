from PIL import Image
import os

dir = 'outputs/20260704/20260704_225729/images'

for fname in ['cover.png', 'inline_1.png']:
    fpath = os.path.join(dir, fname)
    img = Image.open(fpath)
    w, h = img.size
    crop_h = int(h * 0.93)
    cropped = img.crop((0, 0, w, crop_h))
    cropped.save(fpath)
    print(f'[OK] {fname}: {h}->{crop_h}px, cropped {h-crop_h}px')

print('Crop done')
