#include <winsock2.h>
#include "generated/default/psu_init.h"
#include <windows.h>
#include <chrono>
#include <cstring>
#include <stdexcept>
#include <string>
#include <mutex>
#include <unordered_map>
#include <rex/cvar.h>
#include <rex/logging.h>

REXCVAR_DEFINE_BOOL(psu_trace_runtime, false, "PSU", "Trace file opens, save operations and slow waits");
REXCVAR_DEFINE_BOOL(psu_trace_network, false, "PSU",
                    "Trace sign-in and connection calls from the Xbox Live menu");
REXCVAR_DEFINE_BOOL(psu_network_dev_profile, false, "PSU",
                    "Use a simulated online profile at the PSU menu for local development");
REXCVAR_DEFINE_UINT32(psu_network_bridge_port, 15020, "PSU",
                     "Loopback adapter port for this community client");

namespace {
constexpr uint32_t kPsuServiceId = 0x534507E3;
constexpr uint32_t kPsuTitleServerServiceId = 0x534507E8;
constexpr uint32_t kLoopbackIPv4 = 0x7F000001;
constexpr uint16_t kNetworkProbePort = 15020;

std::mutex file_mutex;
std::unordered_map<uint32_t, std::string> movie_files;
PPCFunc* Original(const char* name) {
  const auto error = GetLastError();
  auto fn = reinterpret_cast<PPCFunc*>(GetProcAddress(GetModuleHandleW(L"rexruntime.dll"), name));
  SetLastError(error);
  if (!fn) throw std::runtime_error(std::string("Missing pinned SDK export: ") + name);
  return fn;
}
using Clock = std::chrono::steady_clock;
double Millis(Clock::time_point start) {
  return std::chrono::duration<double, std::milli>(Clock::now()-start).count();
}
std::string GuestString(uint8_t* base, uint32_t address) {
  std::string value;
  if (!address) return value;
  for (unsigned i=0;i<512;i++) {
    char c=static_cast<char>(REX_LOAD_U8(address+i));
    if (!c) break;
    value.push_back(c);
  }
  return value;
}
}

#define PSU_NETWORK_IMPORT(name) \
REX_EXTERN(__imp__##name) { \
  static auto* original = Original("__imp__" #name); \
  const auto caller = ctx.lr; \
  original(ctx, base); \
  if (REXCVAR_GET(psu_trace_network)) \
    REXLOG_INFO("PSU network: " #name " caller={:08X} result={:08X}", caller, ctx.r3.u32); \
}

PSU_NETWORK_IMPORT(XamShowSigninUI)
PSU_NETWORK_IMPORT(XamUserCheckPrivilege)
PSU_NETWORK_IMPORT(NetDll_XNetStartup)
PSU_NETWORK_IMPORT(NetDll_XNetGetTitleXnAddr)
PSU_NETWORK_IMPORT(NetDll_XNetDnsRelease)
PSU_NETWORK_IMPORT(NetDll_WSAStartup)
PSU_NETWORK_IMPORT(NetDll_socket)
PSU_NETWORK_IMPORT(NetDll_recv)
PSU_NETWORK_IMPORT(NetDll_send)
PSU_NETWORK_IMPORT(XamUserGetXUID)
PSU_NETWORK_IMPORT(XamUserReadProfileSettings)

#undef PSU_NETWORK_IMPORT

REX_EXTERN(__imp__NetDll_connect) {
  static auto* original = Original("__imp__NetDll_connect");
  static auto* set_error = Original("__imp__NetDll_WSASetLastError");
  const auto caller = ctx.lr;
  const auto address = ctx.r5.u32;
  const bool loopback = REXCVAR_GET(psu_network_dev_profile) &&
      caller == 0x825B1DF8 && address && ctx.r6.u32 == 16 &&
      REX_LOAD_U16(address) == AF_INET &&
      REX_LOAD_U16(address + 2) == kNetworkProbePort &&
      REX_LOAD_U32(address + 4) == kLoopbackIPv4;
  if (loopback) {
    const auto port = REXCVAR_GET(psu_network_bridge_port);
    if (!port || port > 65535) throw std::runtime_error("Invalid PSU connection adapter port");
    // Keep the guest's discovery and redirect protocol unchanged. Only this
    // client's loopback socket is routed to its own authenticated adapter.
    REX_STORE_U16(address + 2, static_cast<uint16_t>(port));
    WSASetLastError(0);
  }
  original(ctx, base);
  const auto result = ctx.r3.u64;
  const int host_error = loopback && ctx.r3.u32 == UINT32_MAX ? WSAGetLastError() : 0;
  if (loopback) REX_STORE_U16(address + 2, kNetworkProbePort);
  if (host_error) {
    // ReXGlue maps every native connect failure to a generic error. PSU
    // needs WSAEWOULDBLOCK to continue polling its nonblocking socket.
    ctx.r3.u64 = static_cast<uint32_t>(host_error);
    set_error(ctx, base);
    ctx.r3.u64 = result;
  }
  if (REXCVAR_GET(psu_trace_network))
    REXLOG_INFO("PSU network: NetDll_connect caller={:08X} loopback={} result={:08X} host_error={}",
                caller, loopback, ctx.r3.u32, host_error);
}

REX_EXTERN(__imp__NetDll_XNetDnsLookup) {
  static auto* original = Original("__imp__NetDll_XNetDnsLookup");
  const auto caller = ctx.lr;
  const auto name = ctx.r4.u32;
  const auto output = ctx.r6.u32;
  const bool loopback = REXCVAR_GET(psu_network_dev_profile) &&
      caller == 0x825B2EE0 && name && output &&
      std::strncmp(reinterpret_cast<const char*>(base + name), "127.0.0.1", 10) == 0;
  original(ctx, base);
  if (loopback && ctx.r3.u32 == 0) {
    const auto dns = REX_LOAD_U32(output);
    if (dns) {
      REX_STORE_U32(dns + 4, 1);
      REX_STORE_U32(dns + 8, kLoopbackIPv4);
      REX_STORE_U32(dns, 0);
    }
  }
  if (REXCVAR_GET(psu_trace_network))
    REXLOG_INFO("PSU network: XNetDnsLookup caller={:08X} host={} result={:08X}",
                caller, GuestString(base, name), ctx.r3.u32);
}

REX_EXTERN(__imp__NetDll_XNetGetEthernetLinkStatus) {
  static auto* original = Original("__imp__NetDll_XNetGetEthernetLinkStatus");
  if (ctx.lr == 0x8221B5D0 && REXCVAR_GET(psu_network_dev_profile)) {
    // The loopback transport is available without a guest Ethernet adapter.
    ctx.r3.u64 = 1;
    return;
  }
  original(ctx, base);
}

REX_EXTERN(__imp__sub_8239F168);
REX_EXTERN(sub_8239F168) {
  if (!REXCVAR_GET(psu_network_dev_profile) || ctx.lr != 0x82163890) {
    __imp__sub_8239F168(ctx, base);
    return;
  }
  const auto discovery = ctx.r3.u32;
  // Supply one local title server using the guest's 208-byte server entry.
  std::memset(base + discovery + 48, 0, 2080);
  REX_STORE_U32(discovery, 0);
  REX_STORE_U8(discovery + 4, 1);
  REX_STORE_U32(discovery + 48, kLoopbackIPv4);
  REX_STORE_U32(discovery + 2128, 0);
  ctx.r4.u64 = 0;
  sub_8239F020(ctx, base);
}

#define PSU_LOOPBACK_XNET(name, guest_caller, success) \
REX_EXTERN(__imp__##name) { \
  static auto* original = Original("__imp__" #name); \
  const auto caller = ctx.lr; \
  if (REXCVAR_GET(psu_network_dev_profile) && caller == guest_caller && \
      ctx.r4.u32 == kLoopbackIPv4) \
    ctx.r3.u64 = success; \
  else \
    original(ctx, base); \
  if (REXCVAR_GET(psu_trace_network)) \
    REXLOG_INFO("PSU network: " #name " caller={:08X} result={:08X}", caller, ctx.r3.u32); \
}

PSU_LOOPBACK_XNET(NetDll_XNetConnect, 0x8239F0A8, 0)
PSU_LOOPBACK_XNET(NetDll_XNetGetConnectStatus, 0x8239F274, 2)

#undef PSU_LOOPBACK_XNET

REX_EXTERN(__imp__sub_82160F88);
REX_EXTERN(sub_82160F88) {
  if (REXCVAR_GET(psu_trace_network))
    REXLOG_INFO("PSU network: mode transition caller={:08X} state={}", ctx.lr, ctx.r4.u32);
  __imp__sub_82160F88(ctx, base);
}

REX_EXTERN(__imp__sub_825B1C78);
REX_EXTERN(sub_825B1C78) {
  // Disconnect clears the title-server hostname. The Retry path skips title
  // discovery, although the Xbox handoff still reads this 32-byte field.
  // Restore only this development endpoint; other DNS requests remain intact.
  constexpr uint32_t title_server_host = 0x8290F20F;
  if (REXCVAR_GET(psu_network_dev_profile) && ctx.lr == 0x8220B3F0 &&
      ctx.r4.u32 == title_server_host && ctx.r5.u32 == kNetworkProbePort &&
      REX_LOAD_U8(title_server_host) == 0) {
    std::memcpy(base + title_server_host, "127.0.0.1", 10);
    if (REXCVAR_GET(psu_trace_network))
      REXLOG_INFO("PSU network: restored development title server for retry");
  }
  if (REXCVAR_GET(psu_trace_network))
    REXLOG_INFO("PSU network: TCP target caller={:08X} address={:08X} host={} port={}",
                ctx.lr, ctx.r4.u32, GuestString(base, ctx.r4.u32), ctx.r5.u32);
  __imp__sub_825B1C78(ctx, base);
}

REX_EXTERN(__imp__NetDll_XNetServerToInAddr) {
  static auto* original = Original("__imp__NetDll_XNetServerToInAddr");
  const auto caller = ctx.lr;
  if (REXCVAR_GET(psu_network_dev_profile) && ctx.r4.u32 == kLoopbackIPv4 &&
      ctx.r5.u32 == kPsuTitleServerServiceId && ctx.r6.u32) {
    REX_STORE_U32(ctx.r6.u32, kLoopbackIPv4);
    ctx.r3.u64 = 0;
  } else {
    original(ctx, base);
  }
  if (REXCVAR_GET(psu_trace_network))
    REXLOG_INFO("PSU network: XNetServerToInAddr caller={:08X} result={:08X}",
                caller, ctx.r3.u32);
}

REX_EXTERN(__imp__sub_825EE330);
REX_EXTERN(sub_825EE330) {
  const auto caller = ctx.lr;
  if ((caller == 0x82163BA4 || caller == 0x8239FDA4) && ctx.r3.u32 == 247 &&
      REXCVAR_GET(psu_network_dev_profile)) {
    ctx.r3.u64 = 1;
    if (REXCVAR_GET(psu_trace_network))
      REXLOG_INFO("PSU network: development profile content access granted");
    return;
  }
  __imp__sub_825EE330(ctx, base);
}

REX_EXTERN(__imp__sub_82626A90);
REX_EXTERN(sub_82626A90) {
  // This disc's XStringVerify uses packed 6-byte input and 10-byte output
  // records. Its older XLIVEBASE RPC id differs from newer XDK versions.
  if (REXCVAR_GET(psu_network_dev_profile) && ctx.lr == 0x8239CECC &&
      ctx.r3.u32 == 0 && ctx.r5.u32 == 1 && ctx.r6.u32 &&
      ctx.r7.u32 == 10 && ctx.r8.u32) {
    const auto input = ctx.r6.u32;
    const auto count = REX_LOAD_U16(input);
    const auto text = REX_LOAD_U32(input + 2);
    bool valid = text && count > 0 && count <= 511;
    if (valid) {
      for (uint32_t i = 0; i < count; ++i) {
        const auto c = REX_LOAD_U16(text + i * 2);
        if (c < 0x20 || c == 0x7F) valid = false;
      }
    }
    const auto output = ctx.r8.u32;
    REX_STORE_U16(output, 1);
    REX_STORE_U32(output + 2, output + 6);
    REX_STORE_U32(output + 6, valid ? 0 : 0x80070057);
    // Complete synchronously; the guest supports both success and IO_PENDING.
    ctx.r3.u64 = 0;
    if (REXCVAR_GET(psu_trace_network))
      REXLOG_INFO("PSU network: development name validation accepted={}", valid);
    return;
  }
  __imp__sub_82626A90(ctx, base);
}

// This guest helper checks the multiplayer privilege before opening Network
// Mode. The development profile is local and has no Xbox account settings.
REX_EXTERN(__imp__sub_823ED4E0);
REX_EXTERN(sub_823ED4E0) {
  const auto caller = ctx.lr;
  const auto privilege = ctx.r4.u32;
  const auto allowed = ctx.r5.u32;
  if ((caller == 0x82163BE0 || caller == 0x8239FDC8) && privilege == 254 && allowed &&
      REXCVAR_GET(psu_network_dev_profile)) {
    REX_STORE_U32(allowed, 1);
    ctx.r3.u64 = 0;
    if (REXCVAR_GET(psu_trace_network))
      REXLOG_INFO("PSU network: development profile multiplayer privilege granted");
    return;
  }
  __imp__sub_823ED4E0(ctx, base);
}

REX_EXTERN(__imp__XamUserGetSigninState) {
  static auto* original = Original("__imp__XamUserGetSigninState");
  const auto caller = ctx.lr;
  const auto user = ctx.r3.u32;
  original(ctx, base);
  const auto state = ctx.r3.u32;
  // The supported disc checks for online sign-in at the menu and during
  // the transition into Network Mode.
  if ((caller == 0x8239FDEC || caller == 0x82163B74) && user == 0 && state == 1 &&
      REXCVAR_GET(psu_network_dev_profile)) {
    ctx.r3.u64 = 2;
  }
  if (REXCVAR_GET(psu_trace_network) && caller != 0x825F11A8) {
    REXLOG_INFO("PSU network: XamUserGetSigninState caller={:08X} result={:08X} effective={:08X}",
                caller, state, ctx.r3.u32);
  }
}

#define PSU_NETWORK_MESSAGE(name) \
REX_EXTERN(__imp__##name) { \
  static auto* original = Original("__imp__" #name); \
  const auto app = ctx.r3.u32; \
  const auto message = ctx.r4.u32; \
  original(ctx, base); \
  if (app == 0xFC && REXCVAR_GET(psu_trace_network)) \
    REXLOG_INFO("PSU network: " #name " XLIVEBASE message={:08X} result={:08X}", message, ctx.r3.u32); \
}

REX_EXTERN(__imp__XMsgInProcessCall) {
  static auto* original = Original("__imp__XMsgInProcessCall");
  const auto app = ctx.r3.u32;
  const auto message = ctx.r4.u32;
  const auto service_id = ctx.r5.u32;
  const auto info = ctx.r6.u32;
  if (REXCVAR_GET(psu_network_dev_profile) && app == 0xFC &&
      message == 0x00058007 && service_id == kPsuServiceId && info) {
    // Guest X_ONLINE_SERVICE_INFO is a 12-byte record.
    REX_STORE_U32(info, kPsuServiceId);
    REX_STORE_U32(info + 4, kLoopbackIPv4);
    REX_STORE_U16(info + 8, kNetworkProbePort);
    REX_STORE_U16(info + 10, 0);
    ctx.r3.u64 = 0;
  } else {
    original(ctx, base);
  }
  if (app == 0xFC && REXCVAR_GET(psu_trace_network))
    REXLOG_INFO("PSU network: XMsgInProcessCall XLIVEBASE message={:08X} result={:08X}",
                message, ctx.r3.u32);
}

PSU_NETWORK_MESSAGE(XMsgStartIORequest)
PSU_NETWORK_MESSAGE(XMsgStartIORequestEx)

#undef PSU_NETWORK_MESSAGE

REX_EXTERN(__imp__NtCreateFile) {
  static auto* original=Original("__imp__NtCreateFile");
  if (!REXCVAR_GET(psu_trace_runtime)) { original(ctx,base); return; }
  const auto caller=ctx.lr;
  const auto handle_out=ctx.r3.u32;
  std::string path;
  if (ctx.r5.u32) {
    const auto name=REX_LOAD_U32(ctx.r5.u32+4);
    if (name) {
      const auto length=REX_LOAD_U16(name);
      const auto text=REX_LOAD_U32(name+4);
      if (text && length<1024) path.assign(reinterpret_cast<char*>(base+text),length);
    }
  }
  const auto start=Clock::now();
  original(ctx,base);
  if (ctx.r3.u32 == 0 && handle_out) {
    const auto handle=REX_LOAD_U32(handle_out);
    std::lock_guard lock(file_mutex);
    movie_files.erase(handle);
    if (path.find("CDPSU") != std::string::npos) movie_files[handle]=path;
  }
  REXLOG_INFO("PSU file open: path={} result={:08X} caller={:08X} ms={:.3f}",path,ctx.r3.u32,caller,Millis(start));
}

#define PSU_TIMED_IMPORT(name) \
REX_EXTERN(__imp__##name) { \
  static auto* original=Original("__imp__" #name); \
  if (!REXCVAR_GET(psu_trace_runtime)) { original(ctx,base); return; } \
  const auto caller=ctx.lr; const auto start=Clock::now(); \
  original(ctx,base); const double ms=Millis(start); \
  if (ms>=50.0) REXLOG_INFO("PSU slow import: " #name " caller={:08X} result={:08X} ms={:.3f}",caller,ctx.r3.u32,ms); \
}
REX_EXTERN(__imp__NtReadFile) {
  static auto* original=Original("__imp__NtReadFile");
  if (!REXCVAR_GET(psu_trace_runtime)) { original(ctx,base); return; }
  std::string movie;
  {
    std::lock_guard lock(file_mutex);
    auto it=movie_files.find(ctx.r3.u32);
    if (it!=movie_files.end()) movie=it->second;
  }
  const auto offset=ctx.r10.u32 ? REX_LOAD_U64(ctx.r10.u32) : UINT64_MAX;
  const auto length=ctx.r9.u32, buffer=ctx.r8.u32, iosb=ctx.r7.u32;
  const auto caller=ctx.lr;
  const auto start=Clock::now();
  original(ctx,base);
  const auto ms=Millis(start);
  if (!movie.empty()) {
    REXLOG_INFO("PSU movie read: file={} offset={:016X} length={} result={:08X} transferred={} buffer={:08X} ms={:.3f}",
        movie,offset,length,ctx.r3.u32,iosb ? REX_LOAD_U32(iosb+4) : 0,buffer,ms);
  } else if (ms>=50.0) REXLOG_INFO("PSU slow import: NtReadFile caller={:08X} result={:08X} ms={:.3f}",caller,ctx.r3.u32,ms);
}
PSU_TIMED_IMPORT(KeWaitForSingleObject)
PSU_TIMED_IMPORT(KeWaitForMultipleObjects)
PSU_TIMED_IMPORT(NtWaitForSingleObjectEx)
PSU_TIMED_IMPORT(KeDelayExecutionThread)

REX_EXTERN(__imp__NtDuplicateObject) {
  static auto* original=Original("__imp__NtDuplicateObject");
  if (!REXCVAR_GET(psu_trace_runtime)) { original(ctx,base); return; }
  const auto source=ctx.r3.u32, output=ctx.r4.u32;
  original(ctx,base);
  if (ctx.r3.u32==0 && output) {
    std::lock_guard lock(file_mutex);
    auto it=movie_files.find(source);
    if (it!=movie_files.end()) movie_files[REX_LOAD_U32(output)]=it->second;
  }
}

REX_EXTERN(__imp__XamContentCreateEx) {
  static auto* original=Original("__imp__XamContentCreateEx");
  if (!REXCVAR_GET(psu_trace_runtime)) { original(ctx,base); return; }
  const auto caller=ctx.lr;
  const auto flags=ctx.r6.u32;
  const auto root=GuestString(base,ctx.r4.u32);
  const auto start=Clock::now();
  original(ctx,base);
  REXLOG_INFO("PSU content open: root={} flags={:08X} result={:08X} caller={:08X} ms={:.3f}",root,flags,ctx.r3.u32,caller,Millis(start));
}

REX_EXTERN(__imp__XamContentClose) {
  static auto* original=Original("__imp__XamContentClose");
  if (!REXCVAR_GET(psu_trace_runtime)) { original(ctx,base); return; }
  const auto root=GuestString(base,ctx.r3.u32);
  original(ctx,base);
  REXLOG_INFO("PSU content close: root={} result={:08X}",root,ctx.r3.u32);
}

REX_EXTERN(__imp__sub_826CE7A8);
REX_EXTERN(sub_826CE7A8) {
  if (REXCVAR_GET(psu_trace_runtime))
    REXLOG_WARN("PSU Sofdec error callback: player={:08X} code={:08X} caller={:08X}",ctx.r3.u32,ctx.r4.u32,ctx.lr);
  __imp__sub_826CE7A8(ctx,base);
}
