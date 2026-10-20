#include "generated/default/psu_init.h"
#include <windows.h>
#include <chrono>
#include <stdexcept>
#include <string>
#include <rex/cvar.h>
#include <rex/logging.h>

REXCVAR_DEFINE_BOOL(psu_trace_runtime, false, "PSU", "Trace file opens, save operations and slow waits");

namespace {
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

REX_EXTERN(__imp__NtCreateFile) {
  static auto* original=Original("__imp__NtCreateFile");
  if (!REXCVAR_GET(psu_trace_runtime)) { original(ctx,base); return; }
  const auto caller=ctx.lr;
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
PSU_TIMED_IMPORT(NtReadFile)
PSU_TIMED_IMPORT(KeWaitForSingleObject)
PSU_TIMED_IMPORT(KeWaitForMultipleObjects)
PSU_TIMED_IMPORT(NtWaitForSingleObjectEx)
PSU_TIMED_IMPORT(KeDelayExecutionThread)

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
