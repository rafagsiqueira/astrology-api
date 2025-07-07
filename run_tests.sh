#!/bin/bash

echo "Running Cosmic Guru API Tests..."
echo "================================="

# Run the tests with verbose output
python -m pytest test_main.py -v

# Check test results
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed successfully!"
else
    echo ""
    echo "❌ Some tests failed. Please check the output above."
fi