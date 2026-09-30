// prevent linking with symbols introduced in GLIBC 2.35
// because ubuntu 22.04 has glibc 2.35 while redhat 9 has glibc 2.34
// and we want to support both

// print what GLIBC symbol versions are used:
// readelf --dyn-syms -W libopplibs.so | grep GLIBC_2.35

// print all versions for a symbol e.g.:
// readelf --dyn-syms -W /lib/x86_64-linux-gnu/libm.so.6 | grep hypot

#if !defined(SET_GLIBC_LINK_VERSIONS_HEADER) && !defined(__ASSEMBLER__)
#define SET_GLIBC_LINK_VERSIONS_HEADER

#ifdef __x86_64__
  __asm__(".symver hypot,hypot@GLIBC_2.2.5");
#endif
#ifdef __aarch64__
  __asm__(".symver hypot,hypot@GLIBC_2.17");
#endif

#endif
