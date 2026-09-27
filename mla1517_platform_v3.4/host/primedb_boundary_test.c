#define _GNU_SOURCE
#include "primedb_storage.h"
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
static int fail(const char *s){fprintf(stderr,"FAIL: %s\n",s);return 1;}
struct vh { uint64_t magic; uint32_t version, vertex_id; uint64_t capacity, head_cursor; unsigned char reserved[32]; };
int main(void){
 char dir[]="/tmp/mla1517-boundary-XXXXXX", cur[]="/tmp/mla1517-boundary-cur-XXXXXX"; if(!mkdtemp(dir))return fail("dir"); int x=mkstemp(cur);close(x);unlink(cur);
 const uint64_t cap=16777216ULL, bytes=64+cap*64; char path[4096]; snprintf(path,sizeof(path),"%s/vertex_14.db",dir); int fd=open(path,O_CREAT|O_RDWR,0600); if(fd<0)return fail("file"); if(ftruncate(fd,(off_t)bytes))return fail("truncate"); struct vh h={PRIMEDB_STORAGE_MAGIC,PRIMEDB_STORAGE_ABI_VERSION,14,cap,cap,{0}}; if(pwrite(fd,&h,sizeof(h),0)!=sizeof(h))return fail("header"); MLA1517_State s={0};s.d1_nonce=cap-1;s.d7_prime_addr=34;s.d10_cassini=1; off_t last=64+(off_t)(cap-1)*64; if(pwrite(fd,&s,sizeof(s),last)!=sizeof(s))return fail("boundary state"); close(fd);
 setenv("MLA1517_PRIME_DB_MAX_BYTES","2147483648",1); primedb_storage_t *db=primedb_storage_open_with_cursors(dir,1,cur); if(!db)return fail("open"); s.d1_nonce=cap;s.d5_zeckendorf=0;uint64_t slot=0;if(primedb_storage_commit(db,&s,NULL,&slot)!=1||slot!=cap)return fail("boundary growth commit"); int cfd=open(cur,O_RDONLY);unsigned char cm[256];if(read(cfd,cm,sizeof(cm))!=sizeof(cm)||*(uint64_t*)(cm+64+14*8)!=cap+1)return fail("boundary cursor");close(cfd);
 printf("{\"status\":\"PASS\",\"boundary_index\":%llu,\"cursor\":%llu,\"remap_growth\":true}\n",(unsigned long long)cap,(unsigned long long)cap+1);
 primedb_storage_close(db);unlink(cur);for(unsigned i=0;i<20;i++){snprintf(path,sizeof(path),"%s/vertex_%02u.db",dir,i);unlink(path);}rmdir(dir);unsetenv("MLA1517_PRIME_DB_MAX_BYTES");return 0;
}
