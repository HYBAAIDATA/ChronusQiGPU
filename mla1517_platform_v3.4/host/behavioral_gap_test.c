#define _GNU_SOURCE
#include "primedb_storage.h"
#include "telemetry_shm.h"
#include <assert.h>
#include <fcntl.h>
#include <pthread.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

static int fail(const char *s) { fprintf(stderr, "FAIL: %s\n", s); return 1; }
static void state_for(MLA1517_State *s, unsigned i) { memset(s, 0, sizeof(*s)); s->d1_nonce=i; s->d7_prime_addr=34; s->d5_zeckendorf=i & 0x100; s->d10_cassini=(i & 1) ? 1 : -1; }
static void *writer(void *arg) { mla1517_telemetry_t *t=arg; for (unsigned i=0;i<1000;i++) mla1517_telemetry_add_fault(t, 3, 1); return NULL; }
int main(void) {
    char dir[]="/tmp/mla1517-behavior-XXXXXX", cur[]="/tmp/mla1517-cur-XXXXXX", tel[]="/tmp/mla1517-tel-XXXXXX";
    if (!mkdtemp(dir)) return fail("mkdtemp");
    int f=mkstemp(cur); close(f); unlink(cur); f=mkstemp(tel); close(f); unlink(tel);
    setenv("MLA1517_PRIME_DB_MAX_BYTES", "131072", 1); setenv("MLA1517_TELEMETRY_PATH", tel, 1);
    mla1517_telemetry_t *t=mla1517_telemetry_open(tel); primedb_storage_t *db=primedb_storage_open_with_cursors(dir,1,cur);
    if (!t || !db) return fail("open");
    for (unsigned i=0;i<1000;i++) { MLA1517_State s; state_for(&s,i); if (primedb_storage_commit(db,&s,NULL,NULL)!=1) return fail("1000 commits"); }
    pid_t child=fork(); if (child==0) { int fd=open(cur,O_RDONLY); unsigned char *m=mmap(NULL,256,PROT_READ,MAP_SHARED,fd,0); unsigned long long total=0; for(int i=0;i<20;i++) total += *(unsigned long long *)(m+64+i*8); _exit(total==1000?0:2); }
    int status=0; waitpid(child,&status,0); if (!WIFEXITED(status)||WEXITSTATUS(status)!=0) return fail("separate-process shared cursors");
    MLA1517_State bad; state_for(&bad, 1); char vertex_path[4096]; snprintf(vertex_path,sizeof(vertex_path),"%s/vertex_14.db",dir); int fd=open(vertex_path,O_RDWR); int zero=0; off_t off=64+64+offsetof(MLA1517_State,d10_cassini); if (pwrite(fd,&zero,4,off)!=4) return fail("corrupt slot"); close(fd);
    uint64_t matches=0; if (primedb_storage_query_d5(db,14,0,NULL,NULL,&matches)!=0 || matches!=999) return fail("query Cassini recheck");
    unlink("/tmp/mla1517-gap-primary"); unlink("/tmp/mla1517-gap-spill"); mla1517_shm_ring_t *primary=mla1517_shm_open("/tmp/mla1517-gap-primary",1), *spill=mla1517_shm_open("/tmp/mla1517-gap-spill",4); MLA1517_State s; state_for(&s,9);
    if (!primary||!spill||mla1517_shm_push(primary,&s)!=1||mla1517_shm_space(primary)!=0||mla1517_shm_push(spill,&s)!=1) return fail("spill retrieval");
    MLA1517_State out; if (mla1517_shm_pop(spill,&out)!=1 || out.d1_nonce!=9) return fail("spill pop");
    pthread_t th; if (pthread_create(&th,NULL,writer,t)!=0) return fail("writer"); for(unsigned i=0;i<100;i++){ unsigned char snap[960]; int rc; unsigned tries=0; do { rc=mla1517_telemetry_snapshot(tel,snap,sizeof(snap)); } while(rc==-2 && ++tries<100); if(rc!=0) return fail("seqlock snapshot"); if(*(uint64_t*)snap!=MLA1517_TELEMETRY_MAGIC) return fail("snapshot magic"); } pthread_join(th,NULL);
    unsigned char snap[960]; if(mla1517_telemetry_snapshot(tel,snap,sizeof(snap))!=0 || *(uint64_t *)(snap+448+3*8)!=1000) return fail("cassini fault telemetry");
    mla1517_shm_close(primary); mla1517_shm_close(spill); primedb_storage_close(db); mla1517_telemetry_close(t); unlink("/tmp/mla1517-gap-primary"); unlink("/tmp/mla1517-gap-spill"); unlink(cur); unlink(tel); char path[4096]; for(unsigned i=0;i<20;i++){snprintf(path,sizeof(path),"%s/vertex_%02u.db",dir,i);unlink(path);} rmdir(dir); unsetenv("MLA1517_PRIME_DB_MAX_BYTES"); unsetenv("MLA1517_TELEMETRY_PATH");
    puts("{\"status\":\"PASS\",\"shared_cursor_process\":true,\"growth\":true,\"spill\":true,\"query_cassini_recheck\":true,\"seqlock\":true,\"cassini_fault_writer\":true}"); return 0;
}
