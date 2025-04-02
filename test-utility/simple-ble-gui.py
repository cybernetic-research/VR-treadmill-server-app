import asyncio
import tkinter as tk
from tkinter import ttk
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError
import threading

# Constants
DEVICE_NAME = "VR Treadmill"
SERVICE_UUID = "de2f6573-5e52-4a14-b5f3-5e562ea02d70"
CONTROL_CHAR_UUID = "de2f6573-5e52-4a14-b5f3-5e562ea02d71"
STATE_CHAR_UUID = "de2f6573-5e52-4a14-b5f3-5e562ea02d72"

class TreadmillApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VR Treadmill Controller")
        self.client = None
        self.is_connected = False
        self.is_running = False
        
        # Create a new event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Setup threading for async operations
        self.thread = threading.Thread(target=self.start_background_loop, daemon=True)
        self.thread.start()
        
        # UI setup
        self.setup_ui()
    
    def start_background_loop(self):
        # Run the event loop in the background
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def setup_ui(self):
        # Create UI elements
        frame = ttk.Frame(self.root, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status display
        self.status_label = ttk.Label(frame, text="Status: Disconnected")
        self.status_label.grid(row=0, column=0, columnspan=2, pady=10)
        
        self.treadmill_state = ttk.Label(frame, text="Treadmill: Offline")
        self.treadmill_state.grid(row=1, column=0, columnspan=2, pady=10)
        
        # Buttons
        self.connect_button = ttk.Button(frame, text="Connect", command=self.handle_connect)
        self.connect_button.grid(row=2, column=0, pady=5, padx=5)
        
        self.start_button = ttk.Button(frame, text="Start Treadmill", command=self.handle_start, state=tk.DISABLED)
        self.start_button.grid(row=3, column=0, pady=5, padx=5)
        
        self.stop_button = ttk.Button(frame, text="Stop Treadmill", command=self.handle_stop, state=tk.DISABLED)
        self.stop_button.grid(row=3, column=1, pady=5, padx=5)
        
        # Set up periodic UI updates
        self.root.after(1000, self.periodic_update)
    
    def periodic_update(self):
        # Periodic UI update that runs in the main thread
        if self.is_connected:
            asyncio.run_coroutine_threadsafe(self.read_treadmill_state(), self.loop)
        self.root.after(1000, self.periodic_update)
    
    def handle_connect(self):
        # Start the connection process when button is pressed
        if not self.is_connected:
            self.status_label.config(text="Status: Scanning...")
            future = asyncio.run_coroutine_threadsafe(self.connect_to_device(), self.loop)
            future.add_done_callback(self.on_connect_complete)
        else:
            future = asyncio.run_coroutine_threadsafe(self.disconnect_from_device(), self.loop)
            future.add_done_callback(self.on_disconnect_complete)
    
    def on_connect_complete(self, future):
        # Callback for when connect_to_device completes
        try:
            result = future.result()
            if not result:
                self.root.after(0, lambda: self.status_label.config(text="Status: Device not found"))
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
    
    def on_disconnect_complete(self, future):
        # Callback for when disconnect_from_device completes
        try:
            future.result()
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
    
    async def connect_to_device(self):
        # Scan for and connect to the device
        try:
            devices = await BleakScanner.discover()
            target_device = next((d for d in devices if d.name == DEVICE_NAME), None)
            
            if not target_device:
                return False
            
            self.client = BleakClient(target_device.address)
            await self.client.connect()
            
            # Set up notification handler
            await self.client.start_notify(
                STATE_CHAR_UUID, 
                self.notification_handler
            )
            
            self.is_connected = True
            
            # Update UI from the main thread
            self.root.after(0, lambda: [
                self.status_label.config(text="Status: Connected"),
                self.connect_button.config(text="Disconnect"),
                self.start_button.config(state=tk.NORMAL),
                self.stop_button.config(state=tk.NORMAL)
            ])
            
            # Read initial state
            await self.read_treadmill_state()
            return True
            
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
            return False
    
    async def disconnect_from_device(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        
        self.is_connected = False
        self.is_running = False
        
        # Update UI from the main thread
        self.root.after(0, lambda: [
            self.status_label.config(text="Status: Disconnected"),
            self.treadmill_state.config(text="Treadmill: Offline"),
            self.connect_button.config(text="Connect"),
            self.start_button.config(state=tk.DISABLED),
            self.stop_button.config(state=tk.DISABLED)
        ])
    
    def notification_handler(self, sender, data):
        # Handle notifications from the device
        is_on = data[0] == 1
        self.is_running = is_on
        
        # Update UI from the main thread
        self.root.after(0, self.update_treadmill_state)
    
    async def read_treadmill_state(self):
        # Read the current state of the treadmill
        if self.client and self.client.is_connected:
            try:
                value = await self.client.read_gatt_char(STATE_CHAR_UUID)
                self.is_running = value[0] == 1
                
                # Update UI from the main thread
                self.root.after(0, self.update_treadmill_state)
            except BleakError:
                # Connection might be lost
                self.root.after(0, lambda: asyncio.run_coroutine_threadsafe(
                    self.disconnect_from_device(), self.loop))
    
    def update_treadmill_state(self):
        # Update the UI with the current treadmill state
        state_text = "Running" if self.is_running else "Stopped"
        self.treadmill_state.config(text=f"Treadmill: {state_text}")
    
    def handle_start(self):
        # Start the treadmill when button is pressed
        asyncio.run_coroutine_threadsafe(self.start_treadmill(), self.loop)
    
    async def start_treadmill(self):
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(CONTROL_CHAR_UUID, bytearray([1]))
            except BleakError as e:
                self.root.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
    
    def handle_stop(self):
        # Stop the treadmill when button is pressed
        asyncio.run_coroutine_threadsafe(self.stop_treadmill(), self.loop)
    
    async def stop_treadmill(self):
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(CONTROL_CHAR_UUID, bytearray([0]))
            except BleakError as e:
                self.root.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
    
    def on_closing(self):
        # Clean up resources on window close
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.cleanup(), self.loop)
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()
    
    async def cleanup(self):
        # Perform cleanup operations
        if self.client and self.client.is_connected:
            await self.client.disconnect()

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = TreadmillApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
