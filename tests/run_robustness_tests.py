from check_explanations import validate_file

def run_all_tests():
    print("=== ROBUSTNESS TESTS ===")
    validate_file("test_outputs_invalid.json")
    validate_file("../output_explanations.json")

if __name__ == "__main__":
    run_all_tests()
