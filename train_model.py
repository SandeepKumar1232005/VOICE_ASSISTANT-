import os
import glob
import librosa
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

def extract_features(file_name):
    try:
        # Load audio file (resample to 16kHz)
        audio, sample_rate = librosa.load(file_name, sr=16000, duration=2.0)
        # Pad or truncate nicely if needed
        if len(audio) < 16000 * 2:
            audio = np.pad(audio, (0, max(0, 16000 * 2 - len(audio))))
            
        # Extract MFCCs
        mfccs = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=40)
        # Compute mean 
        mfccs_mean = np.mean(mfccs.T, axis=0)
        return mfccs_mean
    except Exception as e:
        print(f"Error encountered while parsing {file_name}: {e}")
        return None

def main():
    base_dir = r"c:\Users\ADMIN\Desktop\VOICEASSISTANT\datasets\jarvis_wake_word"
    
    # Positive examples
    positive_files = glob.glob(os.path.join(base_dir, "positive", "*.wav"))
    # Negative examples (Background noise, random words)
    negative_files = glob.glob(os.path.join(base_dir, "negative", "*.wav"))
    noise_files = glob.glob(os.path.join(base_dir, "noise", "*.wav"))
    
    # Combine negatives and noise into one robust negative class
    all_negatives = negative_files + noise_files
    
    # Limit files for speed to not overload RAM
    print(f"Found {len(positive_files)} Positive, {len(all_negatives)} Negative/Noise files.")
    
    X = []
    y = []

    print("Extracting features (This may take a few minutes)...")
    
    # Load Positive Data (Class 1)
    for index, file in enumerate(positive_files):
        feature = extract_features(file)
        if feature is not None:
            X.append(feature)
            y.append(1)
        if index % 200 == 0 and index > 0:
            print(f"Processed {index} positive files...")

    # Load Negative Data (Class 0)
    for index, file in enumerate(all_negatives):
        feature = extract_features(file)
        if feature is not None:
            X.append(feature)
            y.append(0)
        if index % 500 == 0 and index > 0:
            print(f"Processed {index} negative files...")

    X = np.array(X)
    y = np.array(y)

    print(f"\nTotal Dataset Shape: {X.shape}")
    if len(X) == 0:
        print("No files found or loaded properly!")
        return
    
    # Split Dataset
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train the Model
    print("\nTraining Artificial Intelligence model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    # Evaluate Model
    print("\nEvaluating Model on Unknown Data:")
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(classification_report(y_test, predictions, target_names=["Negative", "Positive"]))
    
    # Save Model
    model_path = os.path.join(os.path.dirname(base_dir), "jarvis_rf_model.pkl")
    joblib.dump(model, model_path)
    print(f"\nSuccess! Small offline AI Brain saved directly to: {model_path}")

if __name__ == "__main__":
    main()
