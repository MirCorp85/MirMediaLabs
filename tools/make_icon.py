from PIL import Image, ImageDraw, ImageFilter
import math
SS=4
def bgimg(S):
    im=Image.new("RGB",(S,S)); px=im.load()
    for y in range(S):
        for x in range(S):
            v=max(0,1-((x/S-.5)**2+(y/S-.45)**2)**.5*1.5)
            px[x,y]=(int(16+70*v),int(8+20*v),int(8+6*v))
    return im
def sphere(d,cx,cy,r,dark,mid,light,steps=40):
    for i in range(steps,-1,-1):
        t=i/steps; rr=r*(.15+.85*t); ox=-r*.32*(1-t); oy=-r*.36*(1-t)
        col=tuple(int(light[k]+(dark[k]-light[k])*t**1.4) if t>.5 else int(light[k]+(mid[k]-light[k])*t*2) for k in range(3))
        d.ellipse([cx+ox-rr,cy+oy-rr,cx+ox+rr,cy+oy+rr],fill=col)
def ring_pts(c,rx,ry,ang,a0,a1,n=260):
    ar=math.radians(ang); out=[]
    for i in range(n+1):
        t=a0+(a1-a0)*i/n; ex,ey=rx*math.cos(t),ry*math.sin(t)
        out.append((c+ex*math.cos(ar)-ey*math.sin(ar),c+ex*math.sin(ar)+ey*math.cos(ar),math.sin(t)))
    return out
def draw_ring(im,c,rx,ry,ang,front,w):
    S=im.size[0]; L=Image.new("RGBA",im.size,(0,0,0,0)); d=ImageDraw.Draw(L)
    k=1.0 if front else .5
    for width,col in ((w*1.25,(90,10,0)),(w,(230,60,15)),(w*.55,(255,120,40)),(w*.2,(255,215,150))):
        cc=tuple(int(v*k) for v in col)+(255,)
        o=(w*1.25-width)/2
        d.ellipse([c-rx+o,c-ry+o,c+rx-o,c+ry-o],outline=cc,width=int(width))
    m=Image.new("L",im.size,0); ImageDraw.Draw(m).rectangle([0,c,S,S] if front else [0,0,S,c],fill=255)
    L.putalpha(Image.composite(L.getchannel("A"),Image.new("L",im.size,0),m))
    im.alpha_composite(L.rotate(ang,center=(c,c),resample=Image.BICUBIC))
def mark(sz,pad,bg=None):
    S=sz*SS; im=(bg.resize((S,S)).convert("RGBA") if bg else Image.new("RGBA",(S,S),(0,0,0,0)))
    c=S/2; R=c*(1-pad); core=R*.58; rx,ry=R,R*.34; w=R*.07
    rings=(0,60,-60)
    for a in rings: draw_ring(im,c,rx,ry,a,False,w)          # back halves
    # glow
    g=Image.new("RGBA",im.size,(0,0,0,0)); ImageDraw.Draw(g).ellipse([c-core*1.25]*2+[c+core*1.25]*2,fill=(255,170,30,110))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(R*.12)))
    d=ImageDraw.Draw(im)
    sphere(d,c,c,core,(205,95,0),(255,205,40),(255,252,215))
    # beveled 3D M
    th=core*.30; x0,x1=c-core*.70,c+core*.70; top,bot,mid=c-core*.74,c+core*.80,c+core*.14
    pts=[(x0,bot),(x0,top),(c,mid),(x1,top),(x1,bot)]
    off=th*.18
    for dx,dy,col,wid in ((off,off,(70,0,0),1.15),(0,0,(150,8,4),1.0),(-off*.4,-off*.4,(225,30,20),.82),(-off*.9,-off*.9,(255,110,90),.28)):
        p=[(x+dx,y+dy) for x,y in pts]
        d.line(p,fill=col,width=int(th*wid),joint="curve")
        for x,y in p: r=th*wid/2; d.ellipse([x-r,y-r,x+r,y+r],fill=col)
    for a in rings: draw_ring(im,c,rx,ry,a,True,w)            # front halves
    d=ImageDraw.Draw(im); er=R*.11
    for ang,pos in ((0,2.6),(60,1.2),(-60,0.55)):
        x,y,_=ring_pts(c,rx,ry,ang,pos,pos,1)[0]
        d.ellipse([x-er*1.1,y-er*1.1+er*.15,x+er*1.1,y+er*1.1+er*.15],fill=(10,30,35))
        sphere(d,x,y,er,(4,70,85),(20,170,190),(220,255,255))
    return im.resize((sz,sz),Image.LANCZOS)
full=mark(1024,.05,bgimg(1024))
full.save("MirMediaLabs-icon-1024.png"); full.resize((512,512),Image.LANCZOS).save(r"server\static\icon-512.png")
full.save("MirMediaLabs.ico",sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
mark(432,.26).save(r"app\app\src\main\res\drawable\ic_fg.png")
bgimg(432).save(r"app\app\src\main\res\drawable\ic_bg.png")
for n,s in (("mdpi",48),("hdpi",72),("xhdpi",96),("xxhdpi",144),("xxxhdpi",192)):
    full.resize((s,s),Image.LANCZOS).save(r"app\app\src\main\res\mipmap-%s\ic_launcher.png"%n)
print("ok")
