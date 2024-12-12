import requests
import pandas as pd
import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns
import chardet
from PIL import Image
import numpy as np
import os

# Retrieve the AI proxy token from the environment variable
AIPROXY_TOKEN = os.getenv('AIPROXY_TOKEN')

if not AIPROXY_TOKEN:
    raise ValueError("AIPROXY_TOKEN environment variable is not set.")

# Use the AIPROXY_TOKEN variable wherever required in your script
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {AIPROXY_TOKEN}"
}


def read_csv_with_fallback(csv_path):
    try:
        with open(csv_path, 'rb') as f:
            result = chardet.detect(f.read())
            encoding = result['encoding']
            df = pd.read_csv(csv_path, encoding=encoding)
            return df
    except Exception as e:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            return df
        except UnicodeDecodeError as ue:
            try:
                df = pd.read_csv(csv_path, encoding='latin1')
                return df
            except Exception as e:
                return None


# Function to summarize numerical data (excluding ID and ISBN columns)
def summarize_numerical_data(df):
    numerical_cols = df.select_dtypes(include=['number']).columns
    numerical_cols = [col for col in numerical_cols if 'id' not in col.lower() and 'isbn' not in col.lower()]
    if not numerical_cols:
        return pd.DataFrame()
    summary = df[numerical_cols].describe().round(2)
    return summary

# Function to calculate correlation matrix
def calculate_correlation(df):
    exclude_keywords = ['title', 'image', 'url', 'path', 'description']
    numerical_cols = [
        col for col in df.select_dtypes(include=['number']).columns
        if not any(keyword in col.lower() for keyword in exclude_keywords)
    ]
    if not numerical_cols:
        return pd.DataFrame()
    correlation_matrix = df[numerical_cols].corr().round(2)
    return correlation_matrix

# Function to generate insights using GPT API
def generate_insights(summary_stats, correlation_matrix):
    try:
        prompt = f"""
        Here is a summary of the dataset:

        Summary Statistics:
        {summary_stats}

        Correlation Matrix:
        {correlation_matrix}

        Based on this data, generate meaningful insights, trends, or suggestions that could be useful for further analysis or business decision-making.
        After generating the insights, suggest 3 to 5 graphs that would help visualize the trends or relationships in the data.
        Please specify only the most relevant and useful graphs for this data.
        """
        url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AIPROXY_TOKEN}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            insights = response.json()['choices'][0]['message']['content']
            return insights
        else:
            return ""
    except Exception as e:
        return ""

# Function to send data (columns, Excel, and README) to LLM
def send_data_to_llm(columns, excel_path, readme_path):
    try:
        prompt = f"""
        Here are the details from a dataset and analysis:

        Column Names: {', '.join(columns)}

        The dataset analysis results are stored in an Excel file at: {excel_path}
        The README file with additional information is located at: {readme_path}

        Please review these files and store the necessary context for future graph evaluations.
        """
        url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AIPROXY_TOKEN}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "Error sending data to LLM."
    except Exception as e:
        return "Error sending data to LLM."

# Function to send the graph for evaluation to LLM
def evaluate_graph_with_llm(graph_path):
    try:
        with open(graph_path, 'rb') as img_file:
            img_data = img_file.read()
        prompt = f"Is the following graph useful and informative for data analysis? Please provide a detailed evaluation."

        url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AIPROXY_TOKEN}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            evaluation = response.json()['choices'][0]['message']['content']
            return evaluation
        else:
            return "Error evaluating graph with LLM."
    except Exception as e:
        return "Error evaluating graph with LLM."

# Function to generate graphs
def generate_graphs(df, output_dir, graph_suggestions):
    numerical_cols = [
        col for col in df.select_dtypes(include=['number']).columns
        if 'id' not in col.lower() and 'isbn' not in col.lower()
    ]
    if not numerical_cols:
        return

    suggestions = graph_suggestions.lower()
    graphs_to_generate = []
    if 'histogram' in suggestions:
        graphs_to_generate.append("histogram")
    if 'scatter plot' in suggestions:
        graphs_to_generate.append("scatter plot")
    if 'correlation heatmap' in suggestions:
        graphs_to_generate.append("correlation heatmap")

    # Generate Graphs
    graph_evaluations = []
    if "histogram" in graphs_to_generate:
        for col in numerical_cols:
            plt.figure(figsize=(10, 6))
            sns.histplot(df[col], kde=True)
            plt.title(f"Distribution of {col}")
            plt.xlabel(col)
            plt.ylabel("Frequency")
            plt.tight_layout()
            file_path = os.path.join(output_dir, f"{col}_histogram.png")
            plt.savefig(file_path)
            plt.close()
            
            evaluation = evaluate_graph_with_llm(file_path)
            graph_evaluations.append((file_path, evaluation))

    if "scatter plot" in graphs_to_generate:
        corr_matrix = df[numerical_cols].corr().abs()
        upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        high_corr_pairs = [(col1, col2) for col1 in upper_tri.columns for col2 in upper_tri.index if upper_tri.loc[col2, col1] >= 0.5]

        if not high_corr_pairs:
            for i, col_x in enumerate(numerical_cols):
                for j, col_y in enumerate(numerical_cols):
                    if col_x != col_y and j > i:
                        plt.figure(figsize=(10, 6))
                        sns.scatterplot(x=df[col_x], y=df[col_y])
                        plt.title(f"Scatter plot: {col_x} vs {col_y}")
                        plt.xlabel(col_x)
                        plt.ylabel(col_y)
                        plt.tight_layout()
                        file_path = os.path.join(output_dir, f"{col_x}_vs_{col_y}_scatter.png")
                        plt.savefig(file_path)
                        plt.close()
                        
                        evaluation = evaluate_graph_with_llm(file_path)
                        graph_evaluations.append((file_path, evaluation))

        else:
            for col_x, col_y in high_corr_pairs[:5]:
                plt.figure(figsize=(10, 6))
                sns.scatterplot(x=df[col_x], y=df[col_y])
                plt.title(f"Scatter plot: {col_x} vs {col_y}")
                plt.xlabel(col_x)
                plt.ylabel(col_y)
                plt.tight_layout()
                file_path = os.path.join(output_dir, f"{col_x}_vs_{col_y}_scatter.png")
                plt.savefig(file_path)
                plt.close()
                
                evaluation = evaluate_graph_with_llm(file_path)
                graph_evaluations.append((file_path, evaluation))

    if "correlation heatmap" in graphs_to_generate:
        correlation_matrix = df[numerical_cols].corr()
        plt.figure(figsize=(10, 8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt='.2f', linewidths=0.5)
        plt.title("Correlation Heatmap")
        plt.tight_layout()
        file_path = os.path.join(output_dir, "correlation_heatmap.png")
        plt.savefig(file_path)
        plt.close()

        evaluation = evaluate_graph_with_llm(file_path)
        graph_evaluations.append((file_path, evaluation))

    return graph_evaluations

# Main function
def main():
    if len(sys.argv) < 2:
        print("Usage: python autolysis.py <dataset_path>")
        return

    csv_path = sys.argv[1]
    if not os.path.isfile(csv_path):
        print("File does not exist. Please check the file path and try again.")
        return

    folder_name = os.path.splitext(os.path.basename(csv_path))[0]
    output_dir = os.path.join(os.path.dirname(csv_path), folder_name)
    os.makedirs(output_dir, exist_ok=True)

    df = read_csv_with_fallback(csv_path)
    if df is None:
        print("Failed to read the CSV file.")
        return

    numerical_summary = summarize_numerical_data(df)
    correlation_matrix = calculate_correlation(df)
    insights = generate_insights(numerical_summary, correlation_matrix)

    # Send Data to LLM for Reference
    columns = df.columns.tolist()
    excel_path = os.path.join(output_dir, f"{folder_name}_analysis.xlsx")
    readme_path = os.path.join(output_dir, f"{folder_name}.md")
    send_data_to_llm(columns, excel_path, readme_path)

    try:
        # Save files
        original_csv_path = os.path.join(output_dir, f"{folder_name}_original.csv")
        df.to_csv(original_csv_path, index=False, encoding='utf-8')

        summary_excel_path = os.path.join(output_dir, f"{folder_name}_analysis.xlsx")
        with pd.ExcelWriter(summary_excel_path, engine='openpyxl') as writer:
            numerical_summary.to_excel(writer, sheet_name="Numerical_Summary", index=True)
            if not correlation_matrix.empty:
                correlation_matrix.to_excel(writer, sheet_name="Correlation_Analysis", index=True)

        summary_csv_path = os.path.join(output_dir, f"{folder_name}_numerical_summary.csv")
        numerical_summary.to_csv(summary_csv_path, index=True, encoding='utf-8')

        if not correlation_matrix.empty:
            correlation_csv_path = os.path.join(output_dir, f"{folder_name}_correlation_matrix.csv")
            correlation_matrix.to_csv(correlation_csv_path, index=True, encoding='utf-8')

        output_md_path = os.path.join(output_dir, f"{folder_name}.md")
        with open(output_md_path, 'w', encoding='utf-8') as md_file:
            md_file.write("# Insights and Analysis\n\n")
            md_file.write(insights)

        print(f"CSV and Markdown files created in: {output_dir}")

    except Exception as e:
        print(f"Error saving files: {e}")

    try:
        # Generate Graphs and Evaluate
        if insights:
            graph_suggestions = "histogram, scatter plot, correlation heatmap"
            graph_evaluations = generate_graphs(df, output_dir, graph_suggestions)

            # Process evaluation results and delete graphs if not useful
            for graph_path, evaluation in graph_evaluations:
                print(f"Graph Evaluation for {graph_path}: {evaluation}")
                if "not useful" in evaluation.lower():
                    os.remove(graph_path)
                    print(f"Deleted graph: {graph_path}")

        else:
            print("No graph suggestions to process.")
    except Exception as e:
        print(f"Error generating graphs: {e}")

    print(f"All graphs created in: {output_dir}")

if __name__ == "__main__":
    main()
