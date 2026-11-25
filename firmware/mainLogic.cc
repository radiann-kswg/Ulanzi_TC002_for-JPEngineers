// FlyThings includes this file from its generated mainActivity translation unit.
#include "tc/screen.h"
#include "tc/fonts.h"
#include "pages/PageBase.h"
#include "managers/AudioManager.h"
#include "managers/McuManager.h"
#include "manager/ConfigManager.h"
#include "os/SystemProperties.h"
#include "base/wifi.h"
#include <arpa/inet.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <chrono>
#include <fstream>
#include <mutex>
#include <sstream>
#include <iomanip>
#include <thread>

namespace {
using namespace tc;
Clock app;
Input keys;
std::mutex inputLock;
std::deque<std::pair<Action,Millis>> actions;
struct Led : PageBase {
    void onEnter() override {}
    void onExit() override {}
    void draw() override {}
    void send(const Frame& f) { sendLedData(f.pixels); }
} panel;
std::vector<uint8_t> previous;
Millis lastRead=-10000;
ino_t feedInode=0;
const char* saved="/data/tc002-dev.prefs";
std::thread wifiStartup;
std::string savedValues;
Millis nowMs() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
void keyEvent(int code,int status) {
    std::lock_guard<std::mutex> lock(inputLock);
    Millis now=nowMs();
    Action action=Action::None;
    switch(code) {
    case E_KEYCODE_CLOCKWISE: action=keys.rotate(true); break;
    case E_KEYCODE_ANTI_CLOCKWISE: action=keys.rotate(false); break;
    case E_KEYCODE_KNOB_BUTTON: action=keys.edge(Key::Knob,status!=0,now); break;
    case E_KEYCODE_MIDDLE_BUTTON: action=keys.edge(Key::Center,status!=0,now); break;
    case E_KEYCODE_LEFT_BUTTON: action=keys.edge(Key::Minus,status!=0,now); break;
    case E_KEYCODE_RIGHT_BUTTON: action=keys.edge(Key::Plus,status!=0,now); break;
    }
    if (action!=Action::None && actions.size()<64) actions.emplace_back(action,now);
}
std::string preferences() {
    std::ostringstream s;
    s<<app.world.base<<' '<<app.world.summer<<' '<<app.volume<<' '<<app.timer.minutes<<' '
     <<app.pomo.focus<<' '<<app.pomo.rest<<' '<<app.busy.focus<<' '<<app.busy.rest<<' '
     <<app.feed.hasLocation<<' '<<std::setprecision(10)<<app.feed.latitude<<' '<<app.feed.longitude;
    return s.str();
}
void loadPreferences() {
    int zone,volume,minutes,pf,pr,bf,br;
    bool dst,has; double lat,lon;
    std::ifstream in(saved);
    if (in>>zone>>dst>>volume>>minutes>>pf>>pr>>bf>>br>>has>>lat>>lon) {
        app.world.base=clamp(zone,-720,840); app.world.summer=dst;
        app.volume=clamp(volume,0,6); app.timer.minutes=clamp(minutes,1,1440);
        app.pomo.focus=clamp(pf,1,60); app.pomo.rest=clamp(pr,1,60);
        app.busy.focus=clamp(bf,1,60); app.busy.rest=clamp(br,1,60);
        app.feed.hasLocation=has && std::abs(lat)<=90 && std::abs(lon)<=180;
        app.feed.latitude=lat; app.feed.longitude=lon;
    }
    savedValues=preferences();
}
void saveIfChanged() {
    auto value=preferences();
    if (value==savedValues) return;
    std::string temp=std::string(saved)+".new";
    std::ofstream out(temp); out<<value<<"\n"; out.close();
    if (out && rename(temp.c_str(),saved)==0) savedValues=value;
}
std::string deviceIp() {
    int fd=socket(AF_INET,SOCK_DGRAM,0);
    if (fd<0) return {};
    ifreq req{}; snprintf(req.ifr_name,sizeof req.ifr_name,"wlan0");
    std::string result;
    if (ioctl(fd,SIOCGIFADDR,&req)==0)
        result=inet_ntoa(reinterpret_cast<sockaddr_in*>(&req.ifr_addr)->sin_addr);
    close(fd); return result;
}
void pollHardware(Millis now) {
    if (now-lastRead<1000) return;
    lastRead=now;
    const char* path="/tmp/tc002-dev.feed";
    struct stat st{};
    if (stat(path,&st)==0 && st.st_size>0 && st.st_size<=262144 && feedInode!=st.st_ino) {
        std::ifstream in(path);
        if (readFeed(in,app.feed)) { feedInode=st.st_ino; saveIfChanged(); }
    }
    static Millis nextBattery=0;
    if (now>=nextBattery) {
        app.ip=deviceIp();
        app.battery=McuManager::getInstance().queryBatteryPower().first;
        nextBattery=now+15000;
    }
}
void sound(Sound s) {
    if (s==Sound::None) return;
    static base::MediaPlayer player;
    if (s==Sound::Silence) { player.stop(); return; }
    if (!app.volume) return;
    const char* name=nullptr;
    const char* fallback=nullptr;
    switch(s) {
    case Sound::Tick: name="Clock.mp3"; fallback="tc002/tick.mp3"; break;
    case Sound::Rotate: name="Rotate.mp3"; fallback="tc002/rotate.mp3"; break;
    case Sound::Button: name="Btn.mp3"; fallback="tc002/button.mp3"; break;
    case Sound::Enter: name="Enter.mp3"; fallback="tc002/enter.mp3"; break;
    default: break;
    }
    if (name) {
        player.onCompletion(nullptr);
        player.onError(nullptr);
        const std::string stock=std::string("/res/ui/audio/")+name;
        player.play(access(stock.c_str(),R_OK)==0 ? stock : CONFIGMANAGER->getResFilePath(fallback));
        return;
    }
    const char* tone = s==Sound::Minute?"minute":s==Sound::Hour?"hour":
        s==Sound::Midnight?"midnight":s==Sound::Rest?"rest":s==Sound::Resume?"resume":"alarm";
    std::string rel=std::string("tc002/")+tone;
    std::string path=CONFIGMANAGER->getResFilePath((rel+".mp3").c_str());
    if (access(path.c_str(),R_OK)!=0) path="/tmp/ui/"+rel+".mp3";
    if (access(path.c_str(),R_OK)!=0) path=CONFIGMANAGER->getResFilePath((rel+".wav").c_str());
    if (access("/tmp/EasyUI.cfg",R_OK)==0) {
        std::ofstream trace("/tmp/tc002-dev.cue");
        trace<<time(nullptr)<<" "<<path<<" "<<(access(path.c_str(),R_OK)==0)<<"\n";
        player.onError([path](int code,const std::string&){
            std::ofstream("/tmp/tc002-dev.audio")<<time(nullptr)<<" error "<<code<<" "<<path<<"\n";
        });
        player.onCompletion([path]{
            std::ofstream("/tmp/tc002-dev.audio")<<time(nullptr)<<" completed "<<path<<"\n";
        });
    }
    int result=player.play(path);
    if (result!=0 && access("/tmp/EasyUI.cfg",R_OK)==0)
        std::ofstream("/tmp/tc002-dev.audio")<<time(nullptr)<<" play "<<result<<" "<<path<<"\n";
}
void update() {
    Millis now=nowMs(); time_t utc=time(nullptr);
    std::deque<std::pair<Action,Millis>> batch;
    { std::lock_guard<std::mutex> lock(inputLock); actions.swap(batch); }
    Sound button=Sound::None;
    for (const auto& event: batch) {
        button=app.command(event.first,event.second);
        if (event.first==Action::Quieter || event.first==Action::Louder)
            awtrix::AudioManager::getInstance().setVolume(app.volume);
        if (button==Sound::Silence) sound(button);
    }
    if (!batch.empty()) saveIfChanged();
    pollHardware(now);
    auto cue=app.advance(now,utc);
    if (cue!=Sound::None) sound(cue);
    else if (!app.alarmActive && button!=Sound::Silence) sound(button);
    Layout view=screen(app,now,utc);
    static Layout last;
    static Millis animationTime=0,entered=-1,redrawAt=0;
    static int nextStep=0,advanceAfter=0;
    bool same=!previous.empty() && entered==app.entered && view.main==last.main && view.sub==last.sub &&
        view.service==last.service && view.servicePage==last.servicePage && view.menu==last.menu && view.popup==last.popup &&
        view.stampLine==last.stampLine && view.gauge==last.gauge && view.weekday==last.weekday &&
        view.color==last.color && view.compact==last.compact && view.icon==last.icon &&
        view.ready==last.ready && view.paused==last.paused && view.weatherKind==last.weatherKind &&
        view.automatic==last.automatic && view.calendarPanel==last.calendarPanel && view.moonTenths==last.moonTenths;
    if (same && now<redrawAt) return;
    // Present every movement step even if a hardware call delayed this UI tick.
    animationTime=same?animationTime+nextStep:0;
    if (same && advanceAfter && animationTime>=advanceAfter) {
        if (view.popup) {
            app.nextPopup();
            view=screen(app,now,utc);
        } else if (app.autoBrowse(now)) view=screen(app,now,utc);
        animationTime=0;
    }
    Frame frame=paint(view,denki,nega,maru,animationTime);
    nextStep=frame.refreshAfter;
    advanceAfter=frame.advanceAfter;
    if (advanceAfter) nextStep=std::min(nextStep,int(advanceAfter-animationTime));
    redrawAt=now+nextStep;
    last=std::move(view); entered=app.entered;
    if (frame.pixels!=previous) {
        panel.send(frame);
        previous.swap(frame.pixels);
    }
}
}
static S_ACTIVITY_TIMEER REGISTER_ACTIVITY_TIMER_TAB[]={{1,50}};
static void onUI_init() {
    SystemProperties::setString("sys.zkapp.state","running");
    auto& mcu=McuManager::getInstance();
    mcu.initialize(new PixelMcuProto::McuParse("/dev/ttyS1",1500000));
    std::string version; mcu.queryMcuVersion(version);
    bool debug=access("/tmp/EasyUI.cfg",R_OK)==0;
    if (debug) saved="/tmp/tc002-dev.prefs";
    loadPreferences();
    awtrix::AudioManager::getInstance().setVolume(app.volume);
    app.entered=nowMs(); previous.clear();
    KeyManager::getInstance().addKeyEventCallback(keyEvent);
    KeyManager::getInstance().start();
    update();
    if (deviceIp().empty() && !wifiStartup.joinable())
        wifiStartup=std::thread([]{ base::wifiOnAndWait(10); });
    if (debug) { std::ofstream ready("/tmp/tc002-dev.ready"); ready<<getpid()<<"\n"; }
    LOGI_TRACE("TC002Dev ready (MCU %s)",version.c_str());
}
static void onUI_intent(const Intent*) {}
static void onUI_show() {}
static void onUI_hide() {}
static void onUI_quit() {
    KeyManager::getInstance().removeKeyEventCallback(keyEvent);
    KeyManager::getInstance().stop();
    if (wifiStartup.joinable()) wifiStartup.join();
}
static void onProtocolDataUpdate(const SProtocolData&) {}
static bool onUI_Timer(int) { update(); return true; }
static bool onmainActivityTouchEvent(const MotionEvent&) { return false; }
