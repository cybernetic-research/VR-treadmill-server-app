//https://www.youtube.com/watch?v=SEQgnSOUkjw
//https://www.youtube.com/watch?v=mBaS3YnqDaU&t=1s

/*
    Video: https://www.youtube.com/watch?v=oCMOYS71NIU
    Based on Neil Kolban example for IDF: https://github.com/nkolban/esp32-snippets/blob/master/cpp_utils/tests/BLE%20Tests/SampleNotify.cpp
    Ported to Arduino ESP32 by Evandro Copercini
    updated by chegewara

   Create a BLE server that, once we receive a connection, will send periodic notifications.
   The service advertises itself as: 4fafc201-1fb5-459e-8fcc-c5c9c331914b
   And has a characteristic of: beb5483e-36e1-4688-b7f5-ea07361b26a8

   The design of creating the BLE server is:
   1. Create a BLE Server
   2. Create a BLE Service
   3. Create a BLE Characteristic on the Service
   4. Create a BLE Descriptor on the characteristic
   5. Start the service.
   6. Start advertising.

   A connect hander associated with the server starts a background task that performs notification
   every couple of seconds.
*/
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <string>  // Include the string header

BLEServer* pServer = NULL;
BLECharacteristic* pControlCharacteristic = NULL;
BLECharacteristic* pStatusCharacteristic = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;
uint32_t value = 0;

// See the following for generating UUIDs:
// https://www.uuidgenerator.net/

#define VR_TREADMILL_SERVICE_UUID                 "de2f6573-5e52-4a14-b5f3-5e562ea02d70"
#define VR_TREADMILL_CONTROL_CHARACTERISTIC_UUID  "de2f6573-5e52-4a14-b5f3-5e562ea02d71"
#define VR_TREADMILL_STATUS_CHARACTERISTIC_UUID   "de2f6573-5e52-4a14-b5f3-5e562ea02d72"

#define  STOPPED 0
#define RUNNING 1
#define DRIVE_OUTPUT_PIN 13

uint8_t status = STOPPED;
uint8_t control = STOPPED; 

class ConnectionCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
      Serial.println("Client connect");
    };

    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      status = STOPPED;
      control = STOPPED; 
      Serial.println("Client disconnect");
    }

    
};

class Characteristicbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue();
      Serial.print("got: ");
      for (int i = 0; i < value.length(); i++) {
        Serial.print(value[i], HEX);
        Serial.print(" ");  // Add a space between each hex value for readability
      }
      control = value[0]; 
      status = control;
        
    }
};

void setup() {
  pinMode(DRIVE_OUTPUT_PIN, OUTPUT);
  Serial.begin(115200);

  // Create the BLE Device
  BLEDevice::init("VR Treadmill");

  // Create the BLE Server
  pServer = BLEDevice::createServer();
  

  // Create the BLE Service
  BLEService *pService = pServer->createService(VR_TREADMILL_SERVICE_UUID);

  // Create a BLE Characteristic
  pControlCharacteristic = pService->createCharacteristic(
                      VR_TREADMILL_CONTROL_CHARACTERISTIC_UUID,
                      BLECharacteristic::PROPERTY_WRITE       //accept command from other device
                    );

  pStatusCharacteristic = pService->createCharacteristic(
                      VR_TREADMILL_STATUS_CHARACTERISTIC_UUID,  //stream to other device
                      BLECharacteristic::PROPERTY_READ   |
                      BLECharacteristic::PROPERTY_NOTIFY |
                      BLECharacteristic::PROPERTY_INDICATE
                    );
  // https://www.bluetooth.com/specifications/gatt/viewer?attributeXmlFile=org.bluetooth.descriptor.gatt.client_characteristic_configuration.xml
  // Create a BLE Descriptor
  //pControlCharacteristic->addDescriptor(new BLE2902());
  pServer->setCallbacks(new ConnectionCallbacks());
  pControlCharacteristic->setCallbacks(new Characteristicbacks());
  pStatusCharacteristic->addDescriptor(new BLE2902());

  // Start the service
  pService->start();

  // Start advertising
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(VR_TREADMILL_SERVICE_UUID);
  pAdvertising->setScanResponse(false);
  pAdvertising->setMinPreferred(0x0);  // set value to 0x00 to not advertise this parameter
  BLEDevice::startAdvertising();
  Serial.println("Waiting a client connection to notify...");
}


void loop() {
    // notify changed value
    if (deviceConnected) {
        pStatusCharacteristic->setValue((uint8_t*)&status, 1);
        pStatusCharacteristic->notify();

        

        if(control==RUNNING)
        {
          digitalWrite(DRIVE_OUTPUT_PIN,HIGH);
        }
        else
        {
          digitalWrite(DRIVE_OUTPUT_PIN,LOW);
        }

        delay(100); // bluetooth stack will go into congestion, if too many packets are sent, in 6 hours test i was able to go as low as 3ms
    }
    else
    {
      control = STOPPED;
    }
    // disconnecting
    if (!deviceConnected && oldDeviceConnected) {
        delay(500); // give the bluetooth stack the chance to get things ready
        pServer->startAdvertising(); // restart advertising
        Serial.println("start advertising");
        oldDeviceConnected = deviceConnected;
    }
    // connecting
    if (deviceConnected && !oldDeviceConnected) {
        // do stuff here on connecting
        oldDeviceConnected = deviceConnected;
    }
}