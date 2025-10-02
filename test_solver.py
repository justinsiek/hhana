# test_solver.py
"""
Test script to verify TexasSolver works correctly
"""
import subprocess
import os
from pathlib import Path

# Paths
SOLVER_DIR = Path("solver")
SOLVER_EXE = SOLVER_DIR / "console_solver.exe"
RESOURCES_DIR = SOLVER_DIR / "resources"
TEST_CONFIG = RESOURCES_DIR / "text/commandline_sample_input.txt"

# Create output directory if it doesn't exist
OUTPUT_DIR = Path("data/test_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def test_solver_basic():
    """Test the solver with the sample input file"""
    print("=" * 60)
    print("Testing TexasSolver...")
    print("=" * 60)
    
    # Check solver exists
    if not SOLVER_EXE.exists():
        print(f"❌ ERROR: Solver not found at {SOLVER_EXE}")
        return False
    
    print(f"✓ Found solver at {SOLVER_EXE}")
    
    # Check test config exists
    if not TEST_CONFIG.exists():
        print(f"❌ ERROR: Test config not found at {TEST_CONFIG}")
        return False
    
    print(f"✓ Found test config at {TEST_CONFIG}")
    
    # Run solver
    print("\nRunning solver...")
    print("-" * 60)
    
    try:
        # Change to solver directory so relative paths work
        original_dir = os.getcwd()
        os.chdir(SOLVER_DIR)
        
        # Run the console solver with proper arguments
        result = subprocess.run(
            [
                str(SOLVER_EXE.name),
                "--input_file", "resources/text/commandline_sample_input.txt",
                "--resource_dir", "./resources",
                "--mode", "holdem"
            ],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        # Print output
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Check if output file was created
        output_file = Path("output_result.json")
        if output_file.exists():
            print("-" * 60)
            print(f"✓ SUCCESS! Solver completed and created {output_file}")
            print(f"  File size: {output_file.stat().st_size} bytes")
            
            # Show first few lines
            with open(output_file, 'r') as f:
                first_lines = f.read(500)
                print(f"\nFirst 500 chars of output:")
                print(first_lines)
            
            return True
        else:
            print("❌ ERROR: Solver ran but didn't create output file")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ ERROR: Solver timed out after 2 minutes")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Change back to project root
        os.chdir(original_dir)

if __name__ == "__main__":
    success = test_solver_basic()
    
    if success:
        print("\n" + "=" * 60)
        print("✓ TexasSolver is working correctly!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Create baseline/ directory structure")
        print("2. Implement config_generator.py")
        print("3. Start generating solver configs for your abstraction")
    else:
        print("\n" + "=" * 60)
        print("❌ TexasSolver test failed")
        print("=" * 60)