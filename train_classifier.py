import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import pickle

# --- Configuration ---
# The user's log shows the file is named 'mails.csv'.
DATA_FILE = 'mails.csv'
VECTORIZER_FILE = 'vectorizer.pkl'
CLASSIFIER_FILE = 'category_classifier.pkl'

def train_model():
    """
    Loads email data, cleans it, trains a classification model, and saves it.
    """
    try:
        # Load the dataset
        print(f"Loading data from '{DATA_FILE}'...")
        df = pd.read_csv(DATA_FILE)

        # --- FIX: Handle missing values ---
        # The "Input contains NaN" error means there are empty cells in your CSV.
        # This line removes any rows that have missing data in the 'text' or 'category' columns.
        print(f"Original number of records: {len(df)}")
        df.dropna(subset=['text', 'category'], inplace=True)
        print(f"Number of records after cleaning (removing missing values): {len(df)}")

        # Ensure columns are correct after cleaning
        if 'text' not in df.columns or 'category' not in df.columns:
            print("Error: CSV file must contain 'text' and 'category' columns.")
            return
        
        if len(df) == 0:
            print("Error: No valid data left after cleaning. Please check your CSV file.")
            return

        # Separate features (X) and target (y)
        X = df['text']
        y = df['category']
        
        # Create a model pipeline: TF-IDF Vectorizer -> Multinomial Naive Bayes Classifier
        print("Building model pipeline...")
        model = make_pipeline(TfidfVectorizer(), MultinomialNB())

        # Train the model
        print("Training the model...")
        model.fit(X, y)
        print("Model training complete.")

        # Save the trained pipeline (vectorizer and classifier)
        with open(CLASSIFIER_FILE, 'wb') as f:
            pickle.dump(model, f)
        print(f"Model saved to '{CLASSIFIER_FILE}'")
        
        # For demonstration, let's also save the vectorizer separately
        with open(VECTORIZER_FILE, 'wb') as f:
            pickle.dump(model.named_steps['tfidfvectorizer'], f)
        print(f"Vectorizer saved to '{VECTORIZER_FILE}'")

    except FileNotFoundError:
        print(f"Error: The data file '{DATA_FILE}' was not found. Make sure it's in the same directory.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    train_model()
