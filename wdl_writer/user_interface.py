"""This module collects user input."""

import shutil
from user_interface_dicts import data_type_to_topic, input_format_dict, species_dict, tools_dict, operation_topic_dict
from retrieval import keyword_filter_tasks


def main():
    keyword_dictionary = prompt_user_for_keywords()
    doc_ids_to_retrieve = filter_keywords_for_tasks(keyword_dictionary)
    print('\nRETRIEVED TASKS WILL BE:\n', doc_ids_to_retrieve)

    # print ('\n\n---DEBUGGING INFO---')
    # print(keyword_dictionary)


def prompt_user_for_keywords():
    print("\nWelcome to the WILDS WDL Writer!\n")
    print(
        "The WDL Writer is NOT A BIOINFORMATICIAN. You should have an idea what "
        "data you have and the processing steps you need to take. Future versions "
        "may help 'fill in' missing steps but not this MVP."
    )
    print("\nMake selections with ONE workflow in mind.\nEnter numbers separated "
          "by commas (for example: 1,4) unless otherwise stated.\n")

    input("Press Enter to get started. CTRL + C to quit.")

    user_topics_user_prompt = "----\nQ1 of 5: What kind of sequencing data do you have? (usually choose one)"
    format_user_prompt = "----\nQ2 of 5: What format(s) will your input data be in? (enter numbers separated by commas)"
    species_user_prompt = "----\nQ3 of 5: What species is your data from? (choose one)"
    operation_user_prompt = "----\nQ4 of 5: What processing or analysis do you want done? (enter numbers separated by commas)"
    tool_user_prompt = "----\nQ5 of 5 [optional]: Any preferred bioinformatics tools? (enter numbers separated by commas)"

    bio_topic, _ = get_terms_from_user(data_type_to_topic, user_topics_user_prompt)
    format_terms, _ = get_terms_from_user(input_format_dict, format_user_prompt)
    species_terms, _ = get_terms_from_user(species_dict, species_user_prompt)
    operation_terms, op_topic = get_terms_from_user(operation_topic_dict, operation_user_prompt)
    tool_terms, _ = get_terms_from_user(tools_dict, tool_user_prompt, required=False)

    # Combine
    keyword_dict = {
        'bio_topic': bio_topic,
        'op_topic': op_topic,
        'format': format_terms,
        'species': species_terms,
        'operation': operation_terms,
        'tool': tool_terms
        }

    return keyword_dict

def filter_keywords_for_tasks(keyword_dict):

    # Get the tasks to be retrieved, along with other info
    input_filtered_tasks, tool_filtered_tasks, op_filtered_tasks, user_incompatible_tools = keyword_filter_tasks(keyword_dict)

    # Tell user if they entered incompatible things
    if not input_filtered_tasks:
        print("\nNo tasks available for this combination of input sequencing data, format, and species\n")
        return
    if keyword_dict['tool'] and user_incompatible_tools:
        print("\nThese tools have no tasks available for provided inputs:\n",
              user_incompatible_tools)

    final_doc_ids = input_filtered_tasks.union(tool_filtered_tasks).union(op_filtered_tasks)
    return final_doc_ids


def get_terms_from_user(term_dict: dict[str, list[str]], prompt: str, required: bool = True) -> set[str]:
    """Present term_dict keys as menu options, then use to select values (terms)."""

    options = list(term_dict.keys())

    while True:
        print(prompt)
        term_width = shutil.get_terminal_size().columns
        col_width = max(len(f"  {i}. {o}") for i, o in enumerate(options)) + 2
        n_cols = min(len(options), max(1, term_width // col_width))
        n_rows = -(-len(options) // n_cols)  # ceiling division
        for row in range(n_rows):
            for col in range(n_cols):
                idx = col * n_rows + row
                if idx < len(options):
                    print(f"  {idx}. {options[idx]}".ljust(col_width), end="")
            print()

        # Interpret the user inpu
        raw_input = input("> ").strip()

        if not raw_input:
            if not required:
                # Tool selection is optional
                return ([], [])
            print("ERROR: Must choose at least one\n")
            continue
        try:
            indices = [int(x.strip()) for x in raw_input.split(",")]
            if max(indices) > len(options) - 1:
                print('ERROR: Please only select from numbers below and separate with commas')
                continue
            if min(indices) < 0:
                print('ERROR: Please only select from numbers below and separate with commas')
                continue
        except ValueError:
            print("ERROR: Please enter numbers only\n")
            continue

        print(f"Selected: {', '.join(options[i] for i in indices)}\n")

        # Use the indices (keys) to grab all the terms (values) from the dic
        terms_1 = []
        terms_2 = []
        for idx in indices:
            terms_1_to_add = term_dict[options[idx]][0]
            terms_1 += terms_1_to_add
            terms_2_to_add = term_dict[options[idx]][1]
            terms_2 += terms_2_to_add

        # Make into lists of unique values
        terms1 = list(set(terms_1))
        terms2 = list(set(terms_2))

        return terms1, terms2


if __name__ == "__main__":
    main()
