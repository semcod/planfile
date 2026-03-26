#!/bin/bash
# Cleanup script to remove redundant external scripts
# These functionalities are now integrated into the planfile package

echo "Cleaning up redundant external scripts..."
echo "These functionalities are now integrated into the planfile package"
echo ""

# Files to remove (redundant - functionality integrated)
REDUNDANT_FILES=(
    "analyze_files.py"
    "enhanced_analyze.py"
    "generate_planfile.py"
    "generate_from_files.py"
    "auto_generate_planfile.sh"
)

# Files to keep (unique functionality)
KEEP_FILES=(
    "example_standalone.py"
    "demo_planfile_usage.py"
    "practical_planfile_example.py"
    "simple_planfile_demo.py"
    "test_integration.py"
    "planfile_gen"
)

echo "Files to remove (functionality integrated):"
for file in "${REDUNDANT_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file ✓"
    else
        echo "  - $file (not found)"
    fi
done

echo ""
echo "Files to keep (unique functionality):"
for file in "${KEEP_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file ✓"
    else
        echo "  - $file (not found)"
    fi
done

echo ""
read -p "Do you want to remove the redundant files? (y/N) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing redundant files..."
    for file in "${REDUNDANT_FILES[@]}"; do
        if [ -f "$file" ]; then
            rm "$file"
            echo "  Removed: $file"
        fi
    done
    echo "Done!"
else
    echo "Cleanup cancelled."
fi

echo ""
echo "New integrated commands to use instead:"
echo "  planfile generate-from-files     # Instead of generate_from_files.py"
echo "  planfile template                # Instead of parts of generate_planfile.py"
echo "  planfile stats                   # New functionality"
echo "  planfile export                  # New functionality"
echo "  planfile compare                 # New functionality"
echo "  planfile health                  # New functionality"
