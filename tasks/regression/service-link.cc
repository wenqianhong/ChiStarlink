// One directional UDP service link. Samples change ns-3 device serialization
// rate and channel delay. A zero-rate sample closes ingress to this link.
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/traffic-control-module.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <vector>

using namespace ns3;

struct Service {
    Ptr<Socket> sender;
    Ptr<PointToPointNetDevice> device;
    Ptr<PointToPointChannel> channel;
    Time interval;
    Time stop;
    bool available = false;
    uint64_t sent = 0;
    uint64_t bytes = 0;
    std::vector<double> delays;
    static const uint32_t payload = 1000;

    void Sample(uint64_t rate, double delay) {
        available = rate > 0;
        if (available) {
            device->SetDataRate(DataRate(rate));
        }
        channel->SetAttribute("Delay", TimeValue(Seconds(delay)));
    }

    void Send() {
        ++sent;
        if (available) {
            SeqTsHeader stamp;
            stamp.SetSeq(sent);
            Ptr<Packet> packet = Create<Packet>(payload - stamp.GetSerializedSize());
            packet->AddHeader(stamp);
            sender->Send(packet);
        }
        if (Simulator::Now() + interval < stop) {
            Simulator::Schedule(interval, &Service::Send, this);
        }
    }

    void Receive(Ptr<Socket> receiver) {
        while (Ptr<Packet> packet = receiver->Recv()) {
            bytes += packet->GetSize();
            SeqTsHeader stamp;
            packet->RemoveHeader(stamp);
            delays.push_back((Simulator::Now() - stamp.GetTs()).GetSeconds() * 1000);
        }
    }
};

int main(int argc, char** argv) {
    std::string input, output;
    double duration, offered;
    CommandLine cmd;
    cmd.AddValue("input", "Validated time_s rate_bps delay_s rows", input);
    cmd.AddValue("output", "Metrics JSON", output);
    cmd.AddValue("duration", "Duration of offered load (s)", duration);
    cmd.AddValue("offered", "Offered UDP payload rate (Mbps)", offered);
    cmd.Parse(argc, argv);

    NodeContainer nodes;
    nodes.Create(2);
    PointToPointHelper link;
    link.SetQueue("ns3::DropTailQueue<Packet>", "MaxSize", StringValue("4p"));
    NetDeviceContainer devices = link.Install(nodes);
    InternetStackHelper internet;
    internet.Install(nodes);
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = ipv4.Assign(devices);
    TrafficControlHelper traffic;
    traffic.Uninstall(devices);

    Service service;
    service.device = DynamicCast<PointToPointNetDevice>(devices.Get(0));
    service.channel = DynamicCast<PointToPointChannel>(service.device->GetChannel());
    service.stop = Seconds(duration);
    service.interval = Seconds(Service::payload * 8.0 / (offered * 1e6));
    service.sender = Socket::CreateSocket(nodes.Get(0), UdpSocketFactory::GetTypeId());
    service.sender->Connect(InetSocketAddress(interfaces.GetAddress(1), 9000));
    Ptr<Socket> receiver = Socket::CreateSocket(nodes.Get(1), UdpSocketFactory::GetTypeId());
    receiver->Bind(InetSocketAddress(interfaces.GetAddress(1), 9000));
    receiver->SetRecvCallback(MakeCallback(&Service::Receive, &service));

    std::ifstream trace(input);
    double t, delay;
    uint64_t rate, updates = 0;
    while (trace >> t >> rate >> delay) {
        Simulator::Schedule(Seconds(t), &Service::Sample, &service, rate, delay);
        ++updates;
    }
    if (!trace.eof() || !updates) {
        std::cerr << "Unreadable/empty service trace" << std::endl;
        return 1;
    }
    Simulator::ScheduleNow(&Service::Send, &service);
    Simulator::Stop(Seconds(duration));
    Simulator::Run();
    std::sort(service.delays.begin(), service.delays.end());
    std::ofstream result(output);
    result << std::setprecision(12)
           << "{\"engine\":\"ns-3.31 point-to-point/IPv4/UDP\",\"duration_s\":" << duration
           << ",\"sample_count\":" << updates << ",\"offered_mbps\":" << offered
           << ",\"sent_packets\":" << service.sent << ",\"received_packets\":" << service.delays.size()
           << ",\"delivery_ratio\":" << double(service.delays.size()) / service.sent
           << ",\"payload_mbps\":" << service.bytes * 8.0 / (duration * 1e6)
           << ",\"p95_delay_ms\":";
    if (service.delays.empty()) {
        result << "null";
    } else {
        result << service.delays[static_cast<size_t>(std::ceil(.95 * service.delays.size())) - 1];
    }
    result << "}\n";
    Simulator::Destroy();
    return result ? 0 : 1;
}
