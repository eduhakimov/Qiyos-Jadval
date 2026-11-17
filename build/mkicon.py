from PIL import Image, ImageDraw
S=512; im=Image.new('RGBA',(S,S),(0,0,0,0)); d=ImageDraw.Draw(im)
d.rounded_rectangle((16,16,S-16,S-16),radius=110,fill=(79,70,229,255))
# jadval belgisi
x0,y0,x1,y1=112,128,400,392
d.rounded_rectangle((x0,y0,x1,y1),radius=26,fill=(255,255,255,255))
d.rectangle((x0,y0+62,x1,y0+70),fill=(79,70,229,255))
d.rectangle((x0+70,y0,x0+78,y1),fill=(79,70,229,255))
d.rectangle((x0+78,y0+150,x1,y0+156),fill=(199,210,254,255)); d.rectangle((x0,y0+150,x0+70,y0+156),fill=(199,210,254,255))
for yy in (92,116,176,200,224):
    d.rounded_rectangle((x0+96,y0+yy,x1-26-(40 if yy in(116,224) else 0),y0+yy+12),radius=6,fill=(253,186,160,255) if yy<150 else (254,215,170,255))
d.rounded_rectangle((x1-62,y0+84,x1-22,y0+124),radius=10,fill=(249,115,22,255))
im.save('icon.png'); im.save('icon.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
