// FlyThings includes this file from its generated mainActivity translation unit.
#include "tc/screen.h"
#include "tc/time_sync.h"
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
#include <condition_variable>
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
std::mutex syncLock;
std::condition_variable syncWake;
bool stopSync = false;
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
        app.pomo.focus=pomoFocusMinutes(pf); app.pomo.rest=clamp(pr,1,60);
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
        if (readFeed(in,app.feed)) {
            feedInode=st.st_ino;
            // /tmp is cleared on reboot. The incoming snapshot provides UTC when NTP is unavailable.
            if (!usableEpoch(time(nullptr)) && usableEpoch(app.feed.generated)) {
                timespec utc{static_cast<time_t>(app.feed.generated), 0};
                clock_settime(CLOCK_REALTIME, &utc);
            }
            saveIfChanged();
        }
    }
    static Millis nextBattery=0;
    if (now>=nextBattery) {
        app.ip=deviceIp();
        app.battery=McuManager::getInstance().queryBatteryPower().first;
        nextBattery=now+15000;
    }
}
base::MediaPlayer& effectPlayer() {
    static base::MediaPlayer player;
    return player;
}
Sound playing=Sound::None;
void sound(Sound cue) {
    if (cue==Sound::None) return;
    auto& player=effectPlayer();
    if (cue==Sound::Silence || !app.volume) {
        player.stop();
        playing=Sound::None;
        return;
    }
    if (player.isPlaying() && !canInterrupt(playing,cue)) return;
    auto readable=[](const std::string& path) { return access(path.c_str(),R_OK)==0; };
    auto resource=[](const std::string& rel) { return CONFIGMANAGER->getResFilePath(rel.c_str()); };
    auto path=soundPath(cue,resource,readable);
    if (path.empty()) return;
    static const bool debug=readable("/tmp/EasyUI.cfg");
    if (debug) {
        std::ofstream("/tmp/tc002-dev.cue")<<time(nullptr)<<" "<<path<<" 1\n";
        player.onError([path](int code,const std::string&){
            std::ofstream("/tmp/tc002-dev.audio")<<time(nullptr)<<" error "<<code<<" "<<path<<"\n";
        });
        player.onCompletion([path]{
            std::ofstream("/tmp/tc002-dev.audio")<<time(nullptr)<<" completed "<<path<<"\n";
        });
    }
    int result=player.play(path);
    playing=result==0 ? cue : Sound::None;
    if (result!=0 && debug)
        std::ofstream("/tmp/tc002-dev.audio")<<time(nullptr)<<" play "<<result<<" "<<path<<"\n";
}
void update() {
    Millis now=nowMs(); time_t utc=time(nullptr);
    std::deque<std::pair<Action,Millis>> batch;
    { std::lock_guard<std::mutex> lock(inputLock); actions.swap(batch); }
    Sound button=Sound::None;
    for (const auto& event: batch) {
        button=preferSound(button,app.command(event.first,event.second));
        if (event.first==Action::Quieter || event.first==Action::Louder)
            awtrix::AudioManager::getInstance().setVolume(app.volume);
    }
    if (!batch.empty()) saveIfChanged();
    pollHardware(now);
    const bool allowPopup=canInterrupt(playing,Sound::Notification) || !effectPlayer().isPlaying();
    auto cue=app.advance(now,utc,allowPopup);
    if (!app.alarmActive) cue=preferSound(cue,button);
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
    if (same && now<redrawAt) { sound(cue); return; }
    // Present every movement step even if a hardware call delayed this UI tick.
    animationTime=same?animationTime+nextStep:0;
    if (same && advanceAfter && animationTime>=advanceAfter) {
        if (view.popup) {
            cue=preferSound(cue,app.nextPopup(app.mayShowPopup(cue,allowPopup)));
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
    sound(cue);
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
    if (!wifiStartup.joinable()) {
        stopSync=false;
        wifiStartup=std::thread([]{
            if (deviceIp().empty()) base::wifiOnAndWait(10);
            std::unique_lock<std::mutex> lock(syncLock);
            while (!stopSync) {
                lock.unlock();
                bool connected=!deviceIp().empty();
                bool synced=connected && syncNetworkTime();
                lock.lock();
                auto delay=std::chrono::seconds(connected ? (synced ? 21600 : 60) : 1);
                syncWake.wait_for(lock, delay, []{return stopSync;});
            }
        });
    }
    if (debug) { std::ofstream ready("/tmp/tc002-dev.ready"); ready<<getpid()<<"\n"; }
    LOGI_TRACE("TC002Dev ready (MCU %s)",version.c_str());
}
static void onUI_intent(const Intent*) {}
static void onUI_show() {}
static void onUI_hide() {}
static void onUI_quit() {
    KeyManager::getInstance().removeKeyEventCallback(keyEvent);
    KeyManager::getInstance().stop();
    {
        std::lock_guard<std::mutex> lock(syncLock);
        stopSync=true;
    }
    syncWake.notify_all();
    if (wifiStartup.joinable()) wifiStartup.join();
}
static void onProtocolDataUpdate(const SProtocolData&) {}
static bool onUI_Timer(int) { update(); return true; }
static bool onmainActivityTouchEvent(const MotionEvent&) { return false; }
