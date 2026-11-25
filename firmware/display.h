#pragma once
#include <algorithm>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace tc {
struct Glyph {
    uint32_t code;
    uint8_t advance, width;
    uint16_t rows[12], padding;
};
static_assert(sizeof(Glyph)==32,"glyph format");
struct Font {
    const Glyph* data;
    size_t count;
    const uint16_t (*faces)[12];
    Font(const Glyph* glyphs,size_t length,const uint16_t (*inside)[12]=nullptr)
        :data(glyphs),count(length),faces(inside) {}
    const Glyph* find(uint32_t code) const {
        const Glyph* end = data+count;
        const Glyph* it = std::lower_bound(data,end,code,[](const Glyph& g,uint32_t c){return g.code<c;});
        return it!=end && it->code==code ? it : nullptr;
    }
};

inline uint32_t character(const std::string& text, size_t& i) {
    uint8_t c = text[i++];
    if (c < 128) return c;
    int n = c>=0xF0 ? 3 : c>=0xE0 ? 2 : c>=0xC2 ? 1 : 0;
    if (!n || c>0xF4 || i+n>text.size()) return '?';
    uint32_t cp = c & (0x7F >> (n+1));
    for (int j=0;j<n;++j) {
        uint8_t b=text[i];
        if ((b&0xC0)!=0x80) return '?';
        cp=(cp<<6)|(b&63); ++i;
    }
    return cp;
}

struct Frame {
    std::vector<uint8_t> pixels = std::vector<uint8_t>(52*16*3,0);
    int refreshAfter=std::numeric_limits<int>::max();
    int advanceAfter=0;
    void wake(int delay) { refreshAfter=std::min(refreshAfter,std::max(1,delay)); }
    void pixel(int x,int y,uint32_t color) {
        if (x<0 || x>=52 || y<0 || y>=16) return;
        size_t p = (y*52+x)*3;
        pixels[p]=color>>16; pixels[p+1]=color>>8; pixels[p+2]=color;
    }
    void bar(int y,int width,uint32_t color) {
        for (int x=0;x<std::min(52,width);++x) pixel(x,y,color);
    }
    void mask(const uint16_t* rows,int width,int x,int y,uint32_t color,int left=0) {
        for (int row=0;row<12;++row)
            for (int bit=std::max(0,left-x);bit<width && x+bit<52;++bit)
                if (rows[row] & (1u<<bit)) pixel(x+bit,y+row,color);
    }
    void glyph(const Glyph& g,int x,int y,uint32_t color) {
        mask(g.rows,g.width,x,y,color);
    }
};

struct TextRun {
    static constexpr int scrollStepMs=50;
    struct Letter { const Glyph* shape; const uint16_t* inside; };
    std::vector<Letter> glyphs;
    int width=0;
    TextRun(const std::string& text,const Font& font,const Font& fallback) {
      int x=0;
      for (size_t i=0;i<text.size();) {
        const uint32_t cp=character(text,i);
        const Font* source=&font;
        const Glyph* g=source->find(cp);
        if (!g) { source=&fallback; g=source->find(cp); }
        if (!g) { source=&font; g=source->find('?'); }
        if (!g) continue;
        glyphs.push_back({g,source->faces?source->faces[g-source->data]:nullptr});
        width=std::max(width,x+g->width);
        x+=g->advance;
      }
    }
    int readTime(int area) const {
        int gap=std::max(0,width-area);
        return gap?1000+(gap-1)*scrollStepMs+1200:3000;
    }
    int cycleTime(int area) const { return readTime(area)+(area+5)*scrollStepMs; }
    void draw(Frame& frame,int y,uint32_t color,int64_t elapsed,int left=0,bool right=false) const {
        int available=52-left, gap=width-available;
        int origin=right && gap<0?left-gap:left;
        int copies=1;
        if (gap>0) {
            int read=readTime(available),cycle=cycleTime(available);
            int phase=int(std::max<int64_t>(0,elapsed)%cycle);
            if (phase<1000) frame.wake(1000-phase);
            else if (phase<read) {
                int distance=std::min(gap,1+(phase-1000)/scrollStepMs);
                origin-=distance;
                frame.wake(distance==gap?read-phase:scrollStepMs-(phase-1000)%scrollStepMs);
            } else {
                origin-=gap+1+(phase-read)/scrollStepMs;
                copies=2;
                frame.wake(scrollStepMs-(phase-read)%scrollStepMs);
            }
        }
        uint32_t outline=(color>>2)&0x3f3f3f;
        for (int pass=0;pass<2;++pass) for (int copy=0;copy<copies;++copy) {
            int x=origin+copy*(width+6);
            for (const auto& letter:glyphs) {
                const auto& g=*letter.shape;
                if (x>=52) break;
                const uint16_t* rows=pass?letter.inside:g.rows;
                if (rows && x+g.width>left)
                    frame.mask(rows,g.width,x,y,!pass && letter.inside?outline:color,left);
                x+=g.advance;
            }
        }
    }
};
inline void line(Frame& frame,const std::string& text,const Font& font,const Font& fallback,
                 int y,uint32_t color,int64_t elapsed=0) {
    TextRun(text,font,fallback).draw(frame,y,color,elapsed);
}
}
