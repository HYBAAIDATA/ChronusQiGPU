CXX ?= g++
CXXFLAGS ?= -O3 -std=c++20 -Wall -Wextra -mavx2 -mfma -fPIC -Iinclude
LIBNAME = libchronus_igpu

ifeq ($(OS),Windows_NT)
    TARGET = $(LIBNAME).dll
    LDFLAGS += -shared -Wl,--out-implib,$(LIBNAME).a
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        TARGET = $(LIBNAME).dylib
        LDFLAGS += -dynamiclib
    else
        TARGET = $(LIBNAME).so
        LDFLAGS += -shared
    endif
endif

SRCS = src/igpu_simd.cpp src/quantum_superposition.cpp src/exact_lattice.cpp src/c_api.cpp
OBJS = $(SRCS:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET) $(LIBNAME).a $(LIBNAME).so $(LIBNAME).dylib $(LIBNAME).dll

.PHONY: all clean
