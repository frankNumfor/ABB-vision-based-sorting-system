import os
import time
from collections import deque

import cv2
import torch
import torch.nn as nn
from opcua import Client, ua
from torchvision import models, transforms


class VisionSystem:

    def __init__(self, opca_url: str = "opc.tcp://localhost:4840"):
        self._opca_url = opca_url
        self._trigger_varname = "trigger_vision"
        self._result_varname = "vision_result"
        self._result_queue = deque()

    def run(self):
        self._connected = self.connect()
        while self._connected:
            if self._result_queue:
                self._result_var.set_value(
                    ua.Variant(self._result_queue.popleft(), ua.VariantType.Int16)
                )
            time.sleep(0.1)

    def connect(self) -> bool:
        self._client = Client(self._opca_url)
        try:
            self._client.connect()
            print("OPCUA Client connected.")

            subscription = self._client.create_subscription(100, self)

            GVL = self._client.get_root_node().get_child([
                "0:Objects",
                "0:Server",
                "4:CODESYS Control Win V3 x64",
                "3:Resources",
                "4:Application",
                "3:GlobalVars",
                "4:GVL",
            ])

            self._trigger_var = GVL.get_child([f"4:{self._trigger_varname}"])
            subscription.subscribe_data_change(self._trigger_var)

            self._result_var = GVL.get_child([f"4:{self._result_varname}"])
            self._result_var.set_value(ua.Variant(0, ua.VariantType.Int16))

            print("OPCUA Client ready.")
            return True

        except Exception as e:
            print(f"Exception setting up OPCUA communication: {e}")
            return False

    def datachange_notification(self, node, val, data):
        if self._trigger_varname == node.nodeid.Identifier.split('.')[-1]:
            if val is True:
                self.vision_program()
            else:
                self.send_vision_result(0)

    def send_vision_result(self, result: int = 0):
        self._result_queue.append(result)

    def vision_program(self):
        pass


class MyVisionProg(VisionSystem):
    def __init__(self, opca_url="opc.tcp://localhost:4840"):
        super().__init__(opca_url)

        # ==============================
        # EDIT THESE PATHS / SETTINGS
        # ==============================
        self.MODEL_PATH = r"C:\Users\Knightingale\Desktop\PCB DETECT\AI_Version\VIM\sortingSystem\dataset\train\model_output\best_mobilenetv2.pth"
        self.IMAGE_PATH = r"C:\Users\Knightingale\Simumatik\workspace\cameras\Saved_View_2.png"

        # Must match training class order exactly
        self.CLASS_NAMES = ['apples', 'bottles', 'cars', 'cups', 'screwdrivers']

        # PLC result mapping
        self.CLASS_TO_RESULT = {
            'apples': 3,
            'bottles': 2,
            'cars': 5,
            'cups': 4,
            'screwdrivers': 1
        }
        self.UNKNOWN_RESULT = 6

        # Set to False if you do not want image windows
        self.SHOW_IMAGES = True

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        self.model = self.load_model()

    def load_model(self):
        model = models.mobilenet_v2(weights=None)
        model.classifier[1] = nn.Linear(
            model.classifier[1].in_features,
            len(self.CLASS_NAMES)
        )

        state_dict = torch.load(self.MODEL_PATH, map_location=self.device)
        model.load_state_dict(state_dict)

        model = model.to(self.device)
        model.eval()

        print("MobileNetV2 model loaded successfully.")
        return model

    def show_received_image(self, img_bgr, pred_class=None):
        """
        Displays the exact image loaded from Simumatik.
        Shows only the predicted object name on the image.
        """
        display = img_bgr.copy()

        if pred_class is not None:
            text = f"Object: {pred_class}"
            cv2.putText(
                display,
                text,
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2
            )

        cv2.imshow("Received Image from Simumatik", display)

    def predict_image(self, img_bgr):
        if img_bgr is None:
            raise ValueError("Image is None. Check IMAGE_PATH.")

        # Convert OpenCV BGR -> RGB for model
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        input_tensor = self.transform(img_rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(input_tensor)
            probs = torch.softmax(outputs, dim=1)
            confidence, pred_idx = torch.max(probs, dim=1)

        pred_idx = pred_idx.item()
        confidence = confidence.item()
        pred_class = self.CLASS_NAMES[pred_idx]

        return pred_class, confidence

    def vision_program(self):
        try:
            # Small delay so Simumatik finishes writing the image
            time.sleep(0.2)

            if not os.path.exists(self.IMAGE_PATH):
                print(f"Image not found: {self.IMAGE_PATH}")
                self.send_vision_result(self.UNKNOWN_RESULT)
                return

            img = cv2.imread(self.IMAGE_PATH)

            if img is None:
                print("Failed to load image from disk.")
                self.send_vision_result(self.UNKNOWN_RESULT)
                return

            pred_class, confidence = self.predict_image(img)

            if confidence < 0.10:
                print(f"Low confidence ({confidence:.3f}) -> Unrecognized")
                self.send_vision_result(self.UNKNOWN_RESULT)

                if self.SHOW_IMAGES:
                    self.show_received_image(img, "unrecognized")
                    cv2.waitKey(1500)
                    cv2.destroyAllWindows()
                return

            result_value = self.CLASS_TO_RESULT.get(pred_class, self.UNKNOWN_RESULT)
            self.send_vision_result(result_value)

            print(f"Predicted: {pred_class} | Confidence: {confidence:.3f} | Sent PLC value: {result_value}")

            if self.SHOW_IMAGES:
                self.show_received_image(img, pred_class)
                cv2.waitKey(1500)
                cv2.destroyAllWindows()

        except Exception as e:
            print(f"Vision program error: {e}")
            self.send_vision_result(self.UNKNOWN_RESULT)
            cv2.destroyAllWindows()


if __name__ == "__main__":
    vision = MyVisionProg(opca_url="opc.tcp://localhost:4840")
    vision._trigger_varname = "trigger_vision"
    vision._result_varname = "vision_result"
    vision.run()