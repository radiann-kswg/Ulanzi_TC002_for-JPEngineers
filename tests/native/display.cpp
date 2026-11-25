#include "../../firmware/display.h"
#include <cassert>
int main() {
    tc::Glyph chars[]={{'?',8,2,{1},0},{'X',12,2,{3},0},{0x5CF6,12,2,{2},0}};
    tc::Font font{chars,3};
    tc::Frame f;
    tc::TextRun address("XXXXX島",font,font);
    assert(address.width==62);
    address.draw(f,0,0x123456,0);
    assert(f.pixels[0]==0x12 && f.refreshAfter==1000);
    tc::Frame moving,tail,again;
    address.draw(moving,0,0x123456,1000);
    assert(moving.pixels!=f.pixels && moving.refreshAfter==50);
    assert(address.readTime(52)==1000+9*50+1200);
    address.draw(tail,0,0x123456,address.readTime(52)-1);
    assert(tail.pixels[51*3]==0x12 && tail.refreshAfter==1);
    tc::Frame wrap;
    address.draw(wrap,0,0x123456,address.cycleTime(52)-1);
    assert(wrap.pixels[0]==0 && wrap.pixels[3]==0x12);
    address.draw(again,0,0x123456,address.cycleTime(52));
    assert(again.pixels==f.pixels);
    // Every scheduled frame, including the wrap, is either held or shifted one LED.
    for (int elapsed=0;elapsed<address.cycleTime(52);) {
        tc::Frame before,after;
        address.draw(before,0,0x123456,elapsed);
        elapsed+=before.refreshAfter;
        address.draw(after,0,0x123456,elapsed);
        for (int x=0;x<51;++x)
            assert(after.pixels[x*3]==before.pixels[(x+1)*3]);
    }
    tc::Frame empty;
    tc::Glyph edge[]={{'X',3,3,{7,5,7},0}};
    const uint16_t inner[][12]={{0,2,0}};
    tc::Font outline{edge,1,inner};
    tc::line(empty,"X",outline,font,0,0xffffff);
    assert(empty.pixels[0]==63 && empty.pixels[(52+1)*3]==255);
    tc::line(empty,"",font,font,0,0);
    assert(empty.pixels.size()==2496);
    size_t i=0;
    assert(tc::character("\xf0\x9f\x98\x80",i)==0x1f600 && i==4);
    i=0;assert(tc::character("\xe3",i)=='?' && i==1);
}
