import cv2
import numpy as np
import mediapipe as mp
import easyocr
from googletrans import Translator
import os
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TF warnings

from tensorflow.keras.models import load_model
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- Indic Font & UI Helpers ---
def draw_indic_text(img, text, position, font_size=32, color=(0, 255, 0)):
    # Convert OpenCV BGR to PIL RGB
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    try:
        font = ImageFont.truetype("Nirmala.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/Nirmala.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
    draw.text(position, text, font=font, fill=color[::-1]) # RGB
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def show_translation_popup(original, translated):
    root = tk.Tk()
    root.withdraw() # Hide root window
    root.attributes("-topmost", True)
    top = tk.Toplevel(root)
    top.title("Live Translate System - Result")
    top.geometry("600x300")
    top.configure(bg="white")
    tk.Label(top, text="Original:", font=("Arial", 12), bg="white").pack(pady=(20,0))
    tk.Label(top, text=original, font=("Arial", 16), bg="white", wraplength=550).pack()
    tk.Label(top, text="Translated to Target Language:", font=("Arial", 12), bg="white").pack(pady=(20,0))
    tk.Label(top, text=translated, font=("Nirmala UI", 26), fg="blue", bg="white", wraplength=550).pack()
    tk.Button(top, text="Close Window", command=root.destroy, font=("Arial", 12)).pack(pady=20)
    root.mainloop()

# -------------------------------
# Initialize modules
# -------------------------------

translator = Translator()
reader = easyocr.Reader(['en'])

# Setup MediaPipe Hands Task API
base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options,
                                       num_hands=2,
                                       min_hand_detection_confidence=0.7,
                                       min_hand_presence_confidence=0.7,
                                       min_tracking_confidence=0.7)

detector = vision.HandLandmarker.create_from_options(options)

# Load pretrained sign model safely
model_path = "sign_language_model.h5"
if os.path.exists(model_path):
    model = load_model(model_path, compile=False)
else:
    model = None
    print(f"Warning: Model file {model_path} not found.")

labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# -------------------------------
# Sign Language Detection Module
# -------------------------------

def extract_landmarks(hand_landmarks):
    data = []
    for lm in hand_landmarks:
        data.append(lm.x)
        data.append(lm.y)
    return np.array(data)

def sign_language_detection():
    cap = cv2.VideoCapture(0)
    sentence = ""
    last_word = ""
    frames_stable = 0

    print("Press Q to quit, C to clear text")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection_result = detector.detect(mp_image)

        if len(detection_result.hand_landmarks) > 0:
            
            # Draw manual landmarks for ALL hands
            for hand_landmarks in detection_result.hand_landmarks:
                for lm in hand_landmarks:
                    x = int(lm.x * frame.shape[1])
                    y = int(lm.y * frame.shape[0])
                    cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

            letter = ""
            hands = detection_result.hand_landmarks

            if model is not None and False:
                pass
            else:
                # --- ISL Heuristic Classifier (Full Alphabet & Words) ---
                def get_fingers_up(hand):
                    tips = [8, 12, 16, 20]
                    pips = [6, 10, 14, 18]
                    return [hand[tip].y < hand[pip].y for tip, pip in zip(tips, pips)]
                
                def get_dist(lm1, lm2):
                    return ((lm1.x - lm2.x)**2 + (lm1.y - lm2.y)**2)**0.5

                if len(hands) == 1:
                    h1 = hands[0]
                    f1 = get_fingers_up(h1)
                    thumb_ext = abs(h1[4].x - h1[2].x) > 0.05
                    thumb_up = h1[4].y < h1[3].y
                    dist_o = get_dist(h1[4], h1[8])
                    
                    if f1 == [False, False, False, False]:
                        if thumb_ext and thumb_up:
                            letter = " " # SPACE (Thumbs Up)
                        elif thumb_ext and not thumb_up and h1[4].y > h1[8].y:
                            letter = "?" # QUESTION MARK
                        elif h1[8].y > h1[6].y and h1[8].y < h1[5].y and not thumb_ext:
                            letter = "," # COMMA (hooked index)
                        elif dist_o < 0.06:
                            letter = "O"
                        elif get_dist(h1[4], h1[8]) > 0.08 and h1[8].x > h1[0].x: 
                            letter = "C" # C shape
                            
                    elif f1 == [True, False, False, False]:
                        if h1[8].y > h1[5].y and h1[0].y < h1[9].y:
                            letter = "!"
                            
                    elif f1 == [False, False, False, True]:
                        letter = "BACKSPACE" # 1-handed Pinky pointing up
                            
                    elif f1 == [True, True, False, False]:
                        if get_dist(h1[8], h1[12]) > 0.05:
                            letter = " " # SPACE (1-handed Peace Sign)
                        else:
                            letter = "U" # Alternative 1-handed U
                            
                    elif f1 == [True, True, True, True]:
                        if get_dist(h1[8], h1[12]) > 0.05 or get_dist(h1[12], h1[16]) > 0.05:
                            letter = "HELLO" 

                elif len(hands) == 2:
                    # Logic for Two-Handed ISL Gestures
                    h1 = hands[0]
                    h2 = hands[1]
                    f1 = get_fingers_up(h1)
                    f2 = get_fingers_up(h2)
                    
                    # Grouping Hand Shapes
                    f_fist = [False, False, False, False]
                    f_open = [True, True, True, True]
                    f_idx = [True, False, False, False]
                    
                    h1_fist = (f1 == f_fist)
                    h2_fist = (f2 == f_fist)
                    h1_open = (f1 == f_open)
                    h2_open = (f2 == f_open)
                    h1_idx = (f1 == f_idx)
                    h2_idx = (f2 == f_idx)

                    dist_8_8 = get_dist(h1[8], h2[8])
                    dist_0_0 = get_dist(h1[0], h2[0])

                    # Eliminate Overlap Bugs by routing logic through explicit shape categories
                    if h1_idx and h2_idx:
                        # R, E, X, K, Y share this state
                        if get_dist(h1[8], h2[5]) < 0.12 or get_dist(h2[8], h1[5]) < 0.12:
                            letter = "Y" # Index tip at base of other index
                        elif dist_8_8 < 0.06:
                            letter = "E" # Tips touching
                        elif get_dist(h1[6], h2[6]) < 0.08:
                            letter = "X" # Crossed at PIP joints
                        elif get_dist(h1[8], h2[6]) < 0.08 or get_dist(h2[8], h1[6]) < 0.08:
                            letter = "K" # Tip hooked on PIP
                        elif dist_8_8 < 0.14:
                            letter = "R" # Tips crossed
                            
                    elif h1_open and h2_open:
                        # W, H, Z share this. H has priority if wrists near but tips separate
                        if dist_0_0 < 0.35 and dist_8_8 > 0.06:
                            letter = "H" # Both palms flat and close/sliding
                        elif dist_8_8 < 0.06 and get_dist(h1[12], h2[12]) < 0.06:
                            letter = "W" # Interlocked fingers
                        elif get_dist(h1[9], h2[9]) < 0.1:
                            letter = "Z" # Base knuckles touching
                            
                    elif h1_fist and h2_fist:
                        # G, B, Q share this
                        if dist_0_0 < 0.15:
                            letter = "G" # Fists stacked
                        elif dist_8_8 < 0.1:
                            letter = "B" # O shapes touching
                        elif get_dist(h1[8], h2[4]) < 0.1 or get_dist(h2[8], h1[4]) < 0.1:
                            letter = "Q" # O shape to thumb

                    elif (h1_idx and h2_fist) or (h2_idx and h1_fist):
                        # D, P share this (One index up, one fist/O shape)
                        fist = h1 if h1_fist else h2
                        idx = h2 if h1_fist else h1
                        if get_dist(fist[8], idx[8]) < 0.1:
                            letter = "P" # P: O touches tip of index
                        elif get_dist(fist[8], idx[5]) < 0.1:
                            letter = "D" # D: O touches base of index

                    elif (f1 == [False, False, False, True] and f2 == [False, False, False, True]):
                        if get_dist(h1[20], h2[20]) < 0.12:
                            letter = "S" # Pinkies hooked
                            
                    elif (f1[:2] == [True, True] and f2[:2] == [True, True]):
                        if dist_8_8 < 0.12:
                            letter = "F" # Index & middle crossed
                            
                    elif h1_open or h2_open:
                        # I, L, M, N, Th, U, V share palm touching
                        if h1_open and not h2_open:
                            palm, other, f_other = h1, h2, f2
                        else:
                            palm, other, f_other = h2, h1, f1
                            
                        palm_base = palm[0]
                        
                        if f_other == [False, False, False, True] and get_dist(other[20], palm_base) < 0.15:
                            letter = "I" # Pinky to palm
                        elif f_other == [True, False, False, False]:
                            if get_dist(other[8], palm_base) < 0.15:
                                letter = "T" # Index to bottom edge
                            elif abs(other[4].x - other[2].x) > 0.05 and get_dist(other[8], palm_base) < 0.2:
                                letter = "L" # L shape on palm
                        elif f_other == [True, True, True, False] and get_dist(other[12], palm_base) < 0.15:
                            letter = "M" # 3 fingers on palm
                        elif f_other == [True, True, False, False]:
                            if get_dist(other[8], other[12]) > 0.05 and get_dist(other[8], palm_base) < 0.15:
                                letter = "V" # Separated, on palm
                            elif get_dist(other[8], palm_base) < 0.15:
                                letter = "N" # Horizontal fingers on palm

                    # Finally check A cross touching
                    if letter == "" and not (h1_open and h2_open):
                        if get_dist(h1[8], h2[4]) < 0.08 or get_dist(h2[8], h1[4]) < 0.08:
                            letter = "A"

            # Smoothing
            if letter != "":
                if letter == last_word:
                    frames_stable += 1
                else:
                    last_word = letter
                    frames_stable = 0

                if frames_stable == 6:
                    if letter in ["HELLO", "THX", " "]:
                        sentence += " " + letter + " "
                        frames_stable = -15 # Long cooldown to prevent spamming
                    elif letter == "BACKSPACE":
                        if len(sentence) > 0:
                            sentence = sentence[:-1] # Delete the last character
                        frames_stable = -10 # Cooldown
                    else:
                        sentence += letter
                        frames_stable = -8 # Small cooldown for letters

        # --- Subtitle Bar Display ---
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 80), (w, h), (0, 0, 0), -1)
        alpha = 0.6
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

        # Display Text inside the black bar at the bottom
        cv2.putText(frame, "Text: " + sentence.replace("  ", " "), (20, h - 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    
        # Move 'Detecting...' text just above the subtitle bar
        if last_word and 0 <= frames_stable < 6:
            cv2.putText(frame, f"Detecting: {last_word} (Hold...)", (20, h - 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        cv2.imshow("Sign Language Detection", frame)

        key = cv2.waitKey(1)
        if key == ord('q'):
            break
        if key == ord('c'):
            sentence = ""
            last_word = ""

    cap.release()
    cv2.destroyAllWindows()

    return sentence.strip().replace("  ", " ")

# -------------------------------
# Text Detection Module
# -------------------------------

def camera_text_detection():
    cap = cv2.VideoCapture(0)
    detected_text = ""
    current_results = []

    print("--- Camera Text Detection ---")
    print("Point the camera at the text.")
    print("Press 'S' to Scan the current frame.")
    print("Press 'Q' to Quit and use the last scanned text.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display_frame = frame.copy()

        # Draw any currently saved results
        for (bbox, text, prob) in current_results:
            (top_left, top_right, bottom_right, bottom_left) = bbox
            top_left = tuple(map(int, top_left))
            bottom_right = tuple(map(int, bottom_right))

            # Only draw a clean bounding box without floating text
            cv2.rectangle(display_frame, top_left, bottom_right, (0, 255, 0), 2)
            
        # Display the aggregated text cleanly at the bottom
        if detected_text:
            h, w = display_frame.shape[:2]
            cv2.rectangle(display_frame, (0, h - 80), (w, h), (0, 0, 0), -1)
            cv2.putText(display_frame, f"Scanned: {detected_text}", (20, h - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        cv2.putText(display_frame, "Press 'S' to scan text | 'Q' to quit", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("Text Detection", display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            print("Scanning...")
            raw_results = reader.readtext(frame)
            
            frame_text = ""
            current_results = []
            for (bbox, text, prob) in raw_results:
                # Filter out low-accuracy noise
                if prob > 0.25:
                    current_results.append((bbox, text, prob))
                    frame_text += text + " "
            
            detected_text = frame_text.strip()
            if detected_text:
                print(f"Scanned Text: {detected_text}")
            else:
                print("No text detected in this frame. Try again.")

    cap.release()
    cv2.destroyAllWindows()

    return detected_text

# -------------------------------
# Translation Module
# -------------------------------

def translate_text(text, target_language="ml"):
    if not text.strip():
        return "No text provided"
    try:
        translated = translator.translate(text, dest=target_language)
        return translated.text
    except Exception as e:
        return f"Translation error: {e}"

# -------------------------------
# Main Program
# -------------------------------

def main():
    while True:
        print("\n=== Live Translate System ===")
        print("1. Sign Language Input (ISL)")
        print("2. Camera Text Detection")
        print("3. Exit")

        choice = input("Choose mode (1/2/3): ")

        if choice == "3":
            print("Exiting...")
            break

        if choice == "1":
            text = sign_language_detection()
            print("\nDetected English Text:", text)
            language = input("Enter target language code (ml/hi/ta/fr): ")
            if language:
                print("Translating...")
                translated = translate_text(text, language)
                print("\nTranslated Text (Logged to UI):", translated)
                show_translation_popup(text, translated)
                
        elif choice == "2":
            text = camera_text_detection()
            print("\nDetected English Text:", text)
            language = input("Enter target language code (ml/hi/ta/fr): ")
            if language:
                print("Translating...")
                translated = translate_text(text, language)
                print("\nTranslated Text (Logged to UI):", translated)
                show_translation_popup(text, translated)
                
        else:
            print("Invalid option")
            continue

if __name__ == "__main__":
    main()