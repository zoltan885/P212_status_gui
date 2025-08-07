import time
import ntplib

def get_time_offset(ntp_server="pool.ntp.org"):
    client = ntplib.NTPClient()
    try:
        response = client.request(ntp_server, version=3)
        ntp_time = response.tx_time
        local_time = time.time()
        offset = ntp_time - local_time
        return offset
    except Exception as e:
        print(f"NTP error: {e}")
        return 0.0  # fallback: no correction