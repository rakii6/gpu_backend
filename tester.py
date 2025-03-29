# Python program to test 
# internet speed 

import speedtest 


st = speedtest.Speedtest()

option = int(input('''What speed do you want to test: 

1) Download Speed 

2) Upload Speed 

3) Ping 

Your Choice: ''')) 


if option == 1: 
    download_speed = st.download() / 1_000_000  # Convert to Mbps
    print(f"Download Speed: {download_speed:.2f} Mbps")

elif option == 2: 
    upload_speed = st.upload() / 1_000_000  # Convert to Mbps
    print(f"Upload Speed: {upload_speed:.2f} Mbps")

elif option == 3: 
    st.get_servers([])
    print(f"Ping: {st.results.ping} ms")

else: 
    print("Please enter the correct choice!")