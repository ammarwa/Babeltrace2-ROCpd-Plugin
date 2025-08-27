# --- file: barectf/Makefile (example) ---
# Adjust PLATFORM_DIR to your linux-fs demo platform clone.
PLATFORM_DIR ?= ./barectf-platform-linux-fs
GEN_DIR      ?= ./gen
CFLAGS := -I$(GEN_DIR)/include -I$(PLATFORM_DIR) -O2 -fPIC
LDFLAGS :=

all: librocpd_barectf.so

librocpd_barectf.so: rocpd_bridge.c
	mkdir -p ./gen
	barectf gen -c ./gen -H ./gen -m ./gen rocpd.yaml
	$(CC) -shared -o $@ $^ $(PLATFORM_DIR)/barectf-platform-linux-fs.c \
		$(GEN_DIR)/barectf.c $(CFLAGS) $(LDFLAGS)

clean:
	rm -rf librocpd_barectf.so ./gen