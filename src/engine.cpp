#include <algorithm>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <list>
#include <map>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <cerrno>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>

using I = int64_t;
namespace fs = std::filesystem;

std::string quote(const std::string& s) {
    std::string out = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { out += '\\'; out += char(c); }
        else if (c < 32) out += ' ';
        else out += char(c);
    }
    return out + "\"";
}

std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> v; size_t start = 0, end;
    while ((end = s.find('\t', start)) != std::string::npos) {
        v.push_back(s.substr(start, end-start)); start=end+1;
    }
    v.push_back(s.substr(start)); return v;
}

I integer(const std::string& s, I low, I high) {
    I n = 0;
    auto [end, error] = std::from_chars(s.data(), s.data()+s.size(), n);
    if (error != std::errc() || end != s.data()+s.size() || n < low || n > high)
        throw std::invalid_argument("integer outside permitted range");
    return n;
}

void identifier(const std::string& s) {
    if (s.empty() || s.size() > 100 || s.find_first_not_of(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-") != std::string::npos)
        throw std::invalid_argument("identifiers require 1-100 ASCII letters, digits, dots, underscores, colons or hyphens");
}

struct Command {
    std::string type, request, id, owner, side, tif;
    I price=0, quantity=0;
    std::string canonical() const {
        std::string s=type+"\t"+request+"\t"+id+"\t"+owner;
        return type=="C" ? s : s+"\t"+side+"\t"+std::to_string(price)+"\t"+std::to_string(quantity)+"\t"+tif;
    }
};

Command parse(const std::string& s) {
    auto v=split(s); Command c;
    if (v.size()!=4 && v.size()!=8) throw std::invalid_argument("wrong command field count");
    c.type=v[0]; c.request=v[1]; c.id=v[2]; c.owner=v[3];
    identifier(c.request); identifier(c.id); identifier(c.owner);
    if (c.type=="O" && v.size()==8) {
        c.side=v[4]; c.price=integer(v[5],1,100000000); c.quantity=integer(v[6],1,100000); c.tif=v[7];
        if ((c.side!="B" && c.side!="S") || (c.tif!="GTC" && c.tif!="IOC"))
            throw std::invalid_argument("invalid side or time in force");
    } else if (c.type!="C" || v.size()!=4) throw std::invalid_argument("unknown command type");
    return c;
}

struct Order { std::string id, owner, side; I price, quantity, sequence; };
struct Trade {
    I id, sequence, price, quantity;
    std::string buyer, seller, maker, taker;
    std::string json() const {
        return "{\"trade_id\":"+std::to_string(id)+",\"sequence\":"+std::to_string(sequence)+
            ",\"price\":"+std::to_string(price)+",\"quantity\":"+std::to_string(quantity)+
            ",\"buyer\":"+quote(buyer)+",\"seller\":"+quote(seller)+",\"maker\":"+quote(maker)+",\"taker\":"+quote(taker)+"}";
    }
};
struct Balance { I cash=0, inventory=0; };
using Queue=std::list<Order>;
struct Location { bool buy; I price; Queue::iterator item; };

class Engine {
public:
    I sequence=0;
    std::map<I,Queue,std::greater<I>> bids;
    std::map<I,Queue> asks;
    std::unordered_map<std::string,Location> index;
    std::unordered_set<std::string> used;
    std::map<std::string,std::pair<std::string,std::string>> requests;
    std::map<std::string,Balance> balances;
    std::vector<Trade> trades;

    std::string duplicate_or_validate(const Command& c) const {
        auto previous=requests.find(c.request);
        if (previous!=requests.end()) {
            if (previous->second.first!=c.canonical()) throw std::invalid_argument("request_id conflicts with an accepted command");
            return previous->second.second;
        }
        if (sequence>=100000) throw std::invalid_argument("100000-command engine limit reached");
        if (c.type=="C") {
            auto o=index.find(c.id);
            if (o==index.end()) throw std::invalid_argument("order is not resting");
            if (o->second.item->owner!=c.owner) throw std::invalid_argument("only the original participant can cancel");
        } else if (used.count(c.id)) throw std::invalid_argument("order_id has already been used");
        return "";
    }

    void add(Order order) {
        if (order.side=="B") {
            auto& q=bids[order.price]; q.push_back(order);
            index[order.id]={true,order.price,std::prev(q.end())};
        } else {
            auto& q=asks[order.price]; q.push_back(order);
            index[order.id]={false,order.price,std::prev(q.end())};
        }
    }

    template<class Book> void match(Order& incoming, Book& book, std::vector<Trade>& fills) {
        while (incoming.quantity && !book.empty()) {
            auto level=book.begin();
            if ((incoming.side=="B" && level->first>incoming.price) ||
                (incoming.side=="S" && level->first<incoming.price)) break;
            auto& maker=level->second.front();
            I size=std::min(incoming.quantity,maker.quantity);
            std::string buyer=incoming.side=="B" ? incoming.owner : maker.owner;
            std::string seller=incoming.side=="S" ? incoming.owner : maker.owner;
            Trade t{I(trades.size())+1,sequence,maker.price,size,buyer,seller,maker.id,incoming.id};
            balances[buyer].inventory+=size; balances[buyer].cash-=size*maker.price;
            balances[seller].inventory-=size; balances[seller].cash+=size*maker.price;
            trades.push_back(t); fills.push_back(t);
            incoming.quantity-=size; maker.quantity-=size;
            if (!maker.quantity) {
                index.erase(maker.id); level->second.pop_front();
                if (level->second.empty()) book.erase(level);
            }
        }
    }

    std::string apply(const Command& c) {
        ++sequence; I resting=0, cancelled=0, filled=0; std::vector<Trade> fills;
        if (c.type=="C") {
            auto location=index.at(c.id); cancelled=location.item->quantity;
            if (location.buy) {
                auto level=bids.find(location.price); level->second.erase(location.item);
                if (level->second.empty()) bids.erase(level);
            } else {
                auto level=asks.find(location.price); level->second.erase(location.item);
                if (level->second.empty()) asks.erase(level);
            }
            index.erase(c.id);
        } else {
            used.insert(c.id);
            Order incoming{c.id,c.owner,c.side,c.price,c.quantity,sequence};
            if (c.side=="B") match(incoming,asks,fills); else match(incoming,bids,fills);
            filled=c.quantity-incoming.quantity;
            if (c.tif=="IOC") cancelled=incoming.quantity;
            else if (incoming.quantity) { resting=incoming.quantity; add(incoming); }
        }
        std::string result="{\"sequence\":"+std::to_string(sequence)+",\"order_id\":"+quote(c.id)+
            ",\"filled\":"+std::to_string(filled)+",\"resting\":"+std::to_string(resting)+
            ",\"cancelled\":"+std::to_string(cancelled)+",\"trades\":[";
        for (size_t i=0;i<fills.size();++i) { if(i)result+=","; result+=fills[i].json(); }
        result+="]}"; requests[c.request]={c.canonical(),result}; return result;
    }

    std::string submit(const Command& c) {
        auto cached=duplicate_or_validate(c); return cached.empty() ? apply(c) : cached;
    }

    std::vector<Order> orders() const {
        std::vector<Order> result;
        for (const auto& [id,location]:index) result.push_back(*location.item);
        std::sort(result.begin(),result.end(),[](const Order& a,const Order& b){return a.sequence<b.sequence;});
        return result;
    }

    template<class Book> std::string levels(const Book& book) const {
        std::string result="["; bool first=true;
        for (const auto& [price,q]:book) {
            I quantity=0; for (const auto& o:q) quantity+=o.quantity;
            if(!first)result+=","; first=false;
            result+="{\"price\":"+std::to_string(price)+",\"quantity\":"+std::to_string(quantity)+",\"orders\":"+std::to_string(q.size())+"}";
        }
        return result+"]";
    }

    std::string state() const {
        std::string result="{\"sequence\":"+std::to_string(sequence)+",\"bids\":"+levels(bids)+",\"asks\":"+levels(asks)+",\"orders\":[";
        auto all=orders();
        for(size_t i=0;i<all.size();++i) {
            const auto& o=all[i]; if(i)result+=",";
            result+="{\"order_id\":"+quote(o.id)+",\"participant\":"+quote(o.owner)+",\"side\":"+quote(o.side=="B"?"buy":"sell")+
                ",\"price\":"+std::to_string(o.price)+",\"quantity\":"+std::to_string(o.quantity)+",\"sequence\":"+std::to_string(o.sequence)+"}";
        }
        result+="],\"trades\":[";
        for(size_t i=0;i<trades.size();++i){if(i)result+=",";result+=trades[i].json();}
        result+="],\"balances\":{"; bool first=true;
        for(const auto& [owner,b]:balances) {
            if(!first)result+=","; first=false;
            result+=quote(owner)+":{\"cash\":"+quote(std::to_string(b.cash))+",\"inventory\":"+std::to_string(b.inventory)+"}";
        }
        return result+"}}";
    }

    std::string dump() const {
        std::string out="SNAPSHOT\t1\t"+std::to_string(sequence)+"\n";
        for(const auto& o:orders())out+="O\t"+o.id+"\t"+o.owner+"\t"+o.side+"\t"+std::to_string(o.price)+"\t"+std::to_string(o.quantity)+"\t"+std::to_string(o.sequence)+"\n";
        std::vector<std::string> ids(used.begin(),used.end());std::sort(ids.begin(),ids.end());
        for(const auto& id:ids)out+="U\t"+id+"\n";
        for(const auto& [owner,b]:balances)out+="B\t"+owner+"\t"+std::to_string(b.cash)+"\t"+std::to_string(b.inventory)+"\n";
        for(const auto& t:trades)out+="T\t"+std::to_string(t.id)+"\t"+std::to_string(t.sequence)+"\t"+std::to_string(t.price)+"\t"+std::to_string(t.quantity)+"\t"+t.buyer+"\t"+t.seller+"\t"+t.maker+"\t"+t.taker+"\n";
        for(const auto& [id,r]:requests)out+="C\t"+r.first+"\nV\t"+r.second+"\n";
        return out;
    }

    void restore(const std::string& payload) {
        std::istringstream in(payload); std::string line, pending;
        if(!std::getline(in,line))throw std::runtime_error("empty snapshot");
        auto header=split(line);
        if(header.size()!=3 || header[0]!="SNAPSHOT" || header[1]!="1")throw std::runtime_error("invalid snapshot header");
        sequence=integer(header[2],0,100000);
        while(std::getline(in,line)) {
            auto v=split(line);
            if(v[0]=="O" && v.size()==7) add({v[1],v[2],v[3],integer(v[4],1,100000000),integer(v[5],1,100000),integer(v[6],1,sequence)});
            else if(v[0]=="U" && v.size()==2)used.insert(v[1]);
            else if(v[0]=="B" && v.size()==4)balances[v[1]]={integer(v[2],-1000000000000000000LL,1000000000000000000LL),integer(v[3],-10000000000LL,10000000000LL)};
            else if(v[0]=="T" && v.size()==9)trades.push_back({integer(v[1],1,10000000000LL),integer(v[2],1,sequence),integer(v[3],1,100000000),integer(v[4],1,100000),v[5],v[6],v[7],v[8]});
            else if(v[0]=="C" && pending.empty())pending=line.substr(2);
            else if(v[0]=="V" && !pending.empty()) {auto c=parse(pending);requests[c.request]={pending,line.substr(2)};pending.clear();}
            else throw std::runtime_error("invalid snapshot record");
        }
        if(!pending.empty() || I(requests.size())!=sequence)throw std::runtime_error("incomplete snapshot");
    }
};

std::string checksum(const std::string& data) {
    uint64_t h=14695981039346656037ULL;
    for(unsigned char c:data){h^=c;h*=1099511628211ULL;}
    std::ostringstream out;out<<std::hex<<h;return out.str();
}
void write_all(int fd,const std::string& data) {
    size_t n=0;
    while(n<data.size()) {
        ssize_t written=::write(fd,data.data()+n,data.size()-n);
        if(written<0 && errno==EINTR)continue;
        if(written<=0)throw std::runtime_error("storage write failed");
        n+=size_t(written);
    }
}
std::string read_file(const fs::path& path) {
    std::ifstream in(path,std::ios::binary);
    if(!in)throw std::runtime_error("cannot read storage file");
    return {std::istreambuf_iterator<char>(in),std::istreambuf_iterator<char>()};
}
void sync_fd(int fd) { if(::fsync(fd)!=0)throw std::runtime_error("fsync failed"); }

class Store {
    fs::path directory,journal,snapshot;
    bool durable,poisoned=false;
    int lock_fd=-1;
    std::string failpoint;
    void sync_directory() {
        int fd=::open(directory.c_str(),O_RDONLY);
        if(fd<0)throw std::runtime_error("cannot open storage directory");
        try {sync_fd(fd);}catch(...){::close(fd);throw;}::close(fd);
    }
    void atomic_file(const fs::path& path,const std::string& data) {
        auto temp=path;temp+=".tmp";
        int fd=::open(temp.c_str(),O_WRONLY|O_CREAT|O_TRUNC,0600);
        if(fd<0)throw std::runtime_error("cannot create snapshot");
        try {write_all(fd,data);sync_fd(fd);}catch(...){::close(fd);throw;}::close(fd);
        if(failpoint=="snapshot_before_rename")::_exit(87);
        fs::rename(temp,path);sync_directory();
    }
public:
    Engine engine;
    Store(const std::string& path="",const std::string& fail=""):durable(!path.empty()),failpoint(fail) {
        if(!durable)return;
        directory=path;fs::create_directories(directory);journal=directory/"commands.log";snapshot=directory/"snapshot.dat";
        lock_fd=::open((directory/"writer.lock").c_str(),O_RDWR|O_CREAT,0600);
        if(lock_fd<0 || ::flock(lock_fd,LOCK_EX|LOCK_NB)!=0) {
            if(lock_fd>=0)::close(lock_fd);
            throw std::runtime_error("data directory already has a writer or cannot be locked");
        }
        try{load();}catch(...){::close(lock_fd);lock_fd=-1;throw;}
    }
    ~Store(){if(lock_fd>=0)::close(lock_fd);}
    Store(const Store&)=delete; Store& operator=(const Store&)=delete;

    void load() {
        poisoned=true;
        engine=Engine();
        std::string data=fs::exists(journal)?read_file(journal):"";
        auto end=data.rfind('\n');size_t valid=end==std::string::npos?0:end+1;
        if(valid!=data.size()) {
            int fd=::open(journal.c_str(),O_WRONLY);
            if(fd<0)throw std::runtime_error("cannot repair torn journal");
            int result=::ftruncate(fd,static_cast<off_t>(valid));
            if(result!=0){::close(fd);throw std::runtime_error("cannot truncate torn journal");}
            try{sync_fd(fd);}catch(...){::close(fd);throw;}::close(fd);
            data.resize(valid);
        }
        if(fs::exists(snapshot)) {
            auto s=read_file(snapshot);auto mark=s.rfind("CHECKSUM\t");
            if(mark==std::string::npos || s.empty() || s.back()!='\n' || checksum(s.substr(0,mark))!=s.substr(mark+9,s.size()-mark-10))
                throw std::runtime_error("snapshot checksum mismatch");
            engine.restore(s.substr(0,mark));
        }
        std::istringstream in(data);std::string line;I count=0;
        while(std::getline(in,line)) {
            auto first=line.find('\t'), last=line.rfind('\t');
            if(first==std::string::npos || first==last || checksum(line.substr(0,last))!=line.substr(last+1))
                throw std::runtime_error("journal checksum mismatch");
            I seq=integer(line.substr(0,first),1,100000);
            if(seq!=++count)throw std::runtime_error("journal sequence gap or duplicate");
            auto c=parse(line.substr(first+1,last-first-1));
            if(seq>engine.sequence) {
                if(!engine.duplicate_or_validate(c).empty())throw std::runtime_error("duplicate request in journal");
                engine.apply(c);
                if(engine.sequence!=seq)throw std::runtime_error("replay sequence mismatch");
            }
        }
        if(engine.sequence>count)throw std::runtime_error("snapshot is ahead of journal");
        poisoned=false;
    }

    std::string submit(const Command& c) {
        if(poisoned)throw std::runtime_error("storage failed; recover or reopen before continuing");
        auto cached=engine.duplicate_or_validate(c);if(!cached.empty())return cached;
        if(durable) {
            if(failpoint=="before_journal")::_exit(85);
            bool existed=fs::exists(journal);
            std::string record=std::to_string(engine.sequence+1)+"\t"+c.canonical();
            record+="\t"+checksum(record)+"\n";
            int fd=::open(journal.c_str(),O_WRONLY|O_APPEND|O_CREAT,0600);
            if(fd<0){poisoned=true;throw std::runtime_error("cannot open journal");}
            try{write_all(fd,record);sync_fd(fd);if(!existed)sync_directory();}
            catch(...){::close(fd);poisoned=true;throw;}::close(fd);
            if(failpoint=="after_journal")::_exit(86);
        }
        try { return engine.apply(c); }
        catch(...) { poisoned=true; throw; }
    }
    void save() {
        if(!durable || poisoned)throw std::runtime_error("snapshot requires healthy durable storage");
        auto payload=engine.dump();atomic_file(snapshot,payload+"CHECKSUM\t"+checksum(payload)+"\n");
    }
};

std::vector<Command> flow(I count) {
    std::mt19937 rng(42);Engine e;std::vector<Command> out;
    for(I i=0;i<count;++i) {
        std::string key="flow-"+std::to_string(i+1);auto orders=e.orders();Command c;
        if(!orders.empty() && rng()%100<15) {
            const auto& o=orders[rng()%orders.size()];
            c={"C",key,o.id,o.owner,"","",0,0};
        } else {
            c={"O",key,key,"agent-"+std::to_string(rng()%4),rng()%2?"B":"S",rng()%100<35?"IOC":"GTC",9995+I(rng()%11),1+I(rng()%8)};
        }
        e.submit(c);out.push_back(c);
    }
    return out;
}

void benchmark(I count,const std::string& directory) {
    auto stream=flow(count);Store store(directory);
    if(store.engine.sequence)throw std::runtime_error("benchmark data directory must be empty");
    std::vector<double> times;I cancels=0,ioc=0,max_depth=0;
    auto start=std::chrono::steady_clock::now();
    for(const auto& c:stream) {
        auto t=std::chrono::steady_clock::now();store.submit(c);
        times.push_back(std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t).count());
        cancels+=c.type=="C";ioc+=c.tif=="IOC";max_depth=std::max(max_depth,I(store.engine.index.size()));
    }
    double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    std::sort(times.begin(),times.end());
    auto percentile=[&](double p){return times[size_t(std::ceil(p*double(times.size())))-1];};
    std::cout<<"{\"commands\":"<<count<<",\"commands_per_second\":"<<count/seconds
        <<",\"latency_us\":{\"p50\":"<<percentile(.50)<<",\"p95\":"<<percentile(.95)<<",\"p99\":"<<percentile(.99)
        <<"},\"cancels\":"<<cancels<<",\"ioc\":"<<ioc<<",\"trades\":"<<store.engine.trades.size()
        <<",\"max_resting_orders\":"<<max_depth<<"}"<<std::endl;
}

int main(int argc,char** argv) {
    try {
        std::string directory,failpoint;I count=0;
        for(int i=1;i<argc;++i) {
            std::string arg=argv[i];
            if(arg=="--data" && i+1<argc)directory=argv[++i];
            else if(arg=="--failpoint" && i+1<argc)failpoint=argv[++i];
            else if(arg=="--benchmark" && i+1<argc)count=integer(argv[++i],1,100000);
            else if(arg=="--memory")directory.clear();
            else throw std::invalid_argument("usage: engine [--memory | --data DIRECTORY] [--benchmark N] [--failpoint NAME]");
        }
        if(count){benchmark(count,directory);return 0;}
        Store store(directory,failpoint);std::string line;
        while(std::getline(std::cin,line)) {
            try {
                if(line.size()>8192)throw std::invalid_argument("command too long");
                if(line=="STATE")std::cout<<"{\"ok\":true,\"state\":"<<store.engine.state()<<"}"<<std::endl;
                else if(line=="SNAPSHOT"){store.save();std::cout<<"{\"ok\":true,\"sequence\":"<<store.engine.sequence<<"}"<<std::endl;}
                else if(line=="RECOVER") {
                    if(directory.empty())throw std::invalid_argument("recovery requires --data");
                    auto before=store.engine.state();store.load();
                    std::cout<<"{\"ok\":true,\"identical\":"<<(before==store.engine.state()?"true":"false")<<",\"state\":"<<store.engine.state()<<"}"<<std::endl;
                } else {
                    auto result=store.submit(parse(line));
                    std::cout<<"{\"ok\":true,\"result\":"<<result<<"}"<<std::endl;
                }
            } catch(const std::exception& e) {
                std::cout<<"{\"ok\":false,\"kind\":"<<quote(dynamic_cast<const std::invalid_argument*>(&e)?"input":"storage")
                    <<",\"error\":"<<quote(e.what())<<"}"<<std::endl;
            }
        }
    } catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
}
