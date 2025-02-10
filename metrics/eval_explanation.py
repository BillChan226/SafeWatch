import os
import json

# Define the folder paths for the model's evaluation results and where to save the output
model_results_path = './result/InternVL2'
output_results_path = './result/exp/InternVL2'

# Function to calculate average rating for a list of ratings
def calculate_average(ratings):
    if not ratings:
        return 0.0
    return sum(ratings) / len(ratings)

# Loop through each model's evaluation JSON file (e.g., gpt-4o_evaluation.json, etc.)
for model_file in os.listdir(model_results_path):
    if model_file.endswith('_evaluation.json'):
        model_name = model_file.replace('_evaluation.json', '')
        model_file_path = os.path.join(model_results_path, model_file)
        
        # Initialize a dictionary to store the averages for subcategories, categories, and overall
        model_averages = {
            "overall_average": 0.0,
            "categories": {}
        }
        total_ratings = []

        # Load the JSON file for the model
        with open(model_file_path, 'r') as f:
            model_data = json.load(f)

        # Loop through each category (C1, C2, etc.) in the model data
        for category, subcategories in model_data.items():
            category_ratings = []
            model_averages["categories"][category] = {
                "category_average": 0.0,
                "subcategories": {}
            }
            
            # Loop through each subcategory within the category
            for subcategory, videos in subcategories.items():
                print("subcategory", subcategory)
                subcategory_ratings = [video['rating'] for video in videos]

                # Calculate the average rating for the subcategory
                subcategory_average = calculate_average(subcategory_ratings)
                model_averages["categories"][category]["subcategories"][subcategory] = {
                    "subcategory_average": subcategory_average
                }
                
                # Add subcategory ratings to category and overall
                category_ratings.extend(subcategory_ratings)
                total_ratings.extend(subcategory_ratings)
            
            # Calculate the average rating for the category
            category_average = calculate_average(category_ratings)
            model_averages["categories"][category]["category_average"] = category_average
        
        # Calculate the overall average rating for the model
        model_averages["overall_average"] = calculate_average(total_ratings)
        
        # Save the results for this model
        output_model_file = os.path.join(output_results_path, f"{model_name}_averages.json")
        os.makedirs(output_results_path, exist_ok=True)
        
        with open(output_model_file, 'w') as output_file:
            json.dump(model_averages, output_file, indent=4)

        print(f"Saved averages for {model_name} to {output_model_file}")
