#!/bin/bash

# === CONFIGURABLE VARIABLES ===
PYDIR="python_embedded"
PYEXE="$PYDIR/bin/python3"
PYPTH="$PYDIR/pyvenv.cfg"
PIP="$PYDIR/bin/pip3"
FFMPEG="$PYDIR/bin/ffmpeg"
BORDER="╔════════════════════════════════════════════════════════════╗"
END="╚════════════════════════════════════════════════════════════╝"

# Detect OS
OS=$(uname -s)
ARCH=$(uname -m)

# Set Python version and download URLs based on OS
PYTHON_VERSION="3.13.5"
case "$OS" in
    "Darwin")
        PLATFORM="macOS"
        if [[ "$ARCH" == "arm64" ]]; then
            PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-macos11.pkg"
            FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/zip"
        else
            PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-macos11.pkg"
            FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/zip"
        fi
        ;;
    "Linux")
        PLATFORM="Linux"
        PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz"
        if [[ "$ARCH" == "x86_64" ]]; then
            FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
        else
            FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
        fi
        ;;
    *)
        echo "Unsupported operating system: $OS"
        exit 1
        ;;
esac

# === UTILITY FUNCTIONS ===
print_header() {
    clear
    echo
    echo "$BORDER"
    echo "║              YOUTUBE DOWNLOADER LAUNCHER                   ║"
    echo "║        Cross-Platform Edition   (Platform: $PLATFORM)        ║"
    echo "║  For Windows: launcher.bat or python launcher.py          ║"
    echo "$END"
    echo
}

print_menu() {
    echo "║  1. Start Web Interface                                    ║"
    echo "║  2. Command Line Help                                      ║"
    echo "║  3. Setup Dependencies                                     ║"
    echo "║  4. Exit                                                   ║"
    echo "$END"
    echo
}

print_section() {
    local msg="$1"
    echo "║  $msg"
    echo "╠════════════════════════════════════════════════════════════╣"
}

print_success() {
    local msg="$1"
    echo "  [SUCCESS] $msg"
}

print_error() {
    local msg="$1"
    echo "  [ERROR] $msg"
}

print_info() {
    local msg="$1"
    echo "  [INFO] $msg"
}

# === PYTHON RUNNER FUNCTION ===
run_python() {
    if [[ -x "$PYEXE" ]]; then
        print_success "Using embedded Python"
        "$PYEXE" "$@"
    elif command -v python3 &> /dev/null; then
        print_success "Using system Python3"
        python3 "$@"
    elif command -v python &> /dev/null; then
        print_success "Using system Python"
        python "$@"
    else
        print_error "Python not found! Please install Python or run setup."
        print_info "Install from: https://python.org"
        read -p "Press Enter to continue..."
        return 1
    fi
}

# === SETUP FUNCTIONS ===
setup_python_venv() {
    if [[ ! -x "$PYEXE" ]]; then
        print_info "Creating Python virtual environment..."
        
        # Check if python3-venv is available on Debian/Ubuntu systems
        if command -v apt &> /dev/null; then
            if ! python3 -c "import venv" &> /dev/null; then
                print_error "Python venv module not found."
                print_info "On Debian/Ubuntu, install with: sudo apt install python3-venv"
                print_info "Or try: sudo apt install python3.10-venv python3.11-venv python3.12-venv"
                return 1
            fi
        fi
        
        # Use system Python to create virtual environment
        if command -v python3 &> /dev/null; then
            python3 -m venv "$PYDIR"
        elif command -v python &> /dev/null; then
            python -m venv "$PYDIR"
        else
            print_error "No Python found on system. Please install Python first."
            return 1
        fi
        
        if [[ -x "$PYEXE" ]]; then
            print_success "Python virtual environment created."
        else
            print_error "Failed to create Python virtual environment."
            print_info "The virtual environment directory exists but Python executable is missing."
            print_info "Removing failed directory and try again."
            rm -rf "$PYDIR"
            return 1
        fi
    else
        print_success "Python virtual environment already exists."
    fi

    # Ensure pip is installed
    if ! "$PYEXE" -m pip --version &> /dev/null; then
        print_info "pip not found, bootstrapping pip..."
        
        # Try to download get-pip.py
        if command -v curl &> /dev/null; then
            curl -O https://bootstrap.pypa.io/get-pip.py
        elif command -v wget &> /dev/null; then
            wget https://bootstrap.pypa.io/get-pip.py
        else
            print_error "curl or wget required to download pip. Please install one of them:"
            print_info "sudo apt install curl"
            print_info "or"
            print_info "sudo apt install wget"
            return 1
        fi
        
        # Check if download was successful
        if [[ -f "get-pip.py" ]]; then
            "$PYEXE" get-pip.py
            if [[ $? -eq 0 ]]; then
                print_success "pip installed successfully."
                rm -f get-pip.py
            else
                print_error "Failed to install pip."
                rm -f get-pip.py
                return 1
            fi
        else
            print_error "Failed to download get-pip.py"
            return 1
        fi
    fi

    # Upgrade pip
    if "$PYEXE" -m pip --version &> /dev/null; then
        print_info "Upgrading pip..."
        "$PYEXE" -m pip install --upgrade pip
    else
        print_error "pip still not available after installation attempt."
        return 1
    fi

    return 0
}

setup_ffmpeg() {
    if [[ ! -x "$FFMPEG" ]]; then
        print_info "Installing FFmpeg..."
        
        case "$OS" in
        "Darwin")
            if command -v brew &> /dev/null; then
                print_info "Installing FFmpeg with Homebrew..."
                brew install ffmpeg
            else
                print_error "Homebrew not found. Install it from https://brew.sh/"
            fi
            ;;
        "Linux")
            if command -v apt &> /dev/null; then
                print_info "Installing FFmpeg with apt..."
                sudo apt update && sudo apt install -y ffmpeg
            else
                print_error "apt not found. Please install FFmpeg manually for your distribution."
            fi
            ;;
        *)
            print_error "Unsupported OS for automatic FFmpeg installation."
            ;;
    esac
    else
        print_success "FFmpeg already present."
    fi
    
    return 0
}

install_requirements() {
    if [[ -f "requirements.txt" ]]; then
        print_info "Installing Python requirements..."
        run_python -m pip install -r requirements.txt
        return $?
    else
        print_error "requirements.txt not found."
        return 1
    fi
}

# === MAIN MENU FUNCTIONS ===
web_interface() {
    clear
    print_header
    print_section "Launching Web Interface..."
    
    # Check if Python is available
    if ! run_python --version &> /dev/null; then
        print_error "Python not available. Please run setup first."
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_info "Starting web server on http://localhost:5005"
    
    # Open browser (platform-specific)
    case "$OS" in
        "Darwin")
            open "http://localhost:5005" &
            ;;
        "Linux")
            if command -v xdg-open &> /dev/null; then
                xdg-open "http://localhost:5005" &
            elif command -v gnome-open &> /dev/null; then
                gnome-open "http://localhost:5005" &
            fi
            ;;
    esac
    
    run_python web_app.py
    read -p "Press Enter to continue..."
}

cli_help() {
    clear
    print_header
    print_section "Command Line Usage"
    echo "║"
    echo "║  python youtube_downloader.py \"VIDEO_URL\" [options]"
    echo "║"
    echo "║  Options:"
    echo "║    -q, --quality     Video quality (best, 4k, 1080p, 720p, 480p, 360p)"
    echo "║    -m, --mode        Download mode (auto, ultra, standard)"
    echo "║    -o, --output      Output filename"
    echo "║    --audio-only      Download audio only"
    echo "║"
    echo "║  Examples:"
    echo "║    python youtube_downloader.py \"https://youtube.com/watch?v=dQw4w9WgXcQ\""
    echo "║    python youtube_downloader.py \"URL\" -q 1080p -m ultra"
    echo "║    python youtube_downloader.py \"URL\" --audio-only"
    echo "║"
    read -p "Press Enter to continue..."
}

setup_dependencies() {
    clear
    print_header
    print_section "Installing dependencies..."
    
    # Setup Python virtual environment
    if ! setup_python_venv; then
        print_error "Failed to setup Python environment."
        read -p "Press Enter to continue..."
        return 1
    fi
    
    # Setup FFmpeg
    if ! setup_ffmpeg; then
        print_error "Failed to setup FFmpeg."
        read -p "Press Enter to continue..."
        return 1
    fi
    
    # Install Python requirements
    if ! install_requirements; then
        print_error "Failed to install Python requirements."
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_success "Setup completed successfully!"
    read -p "Press Enter to continue..."
}

cleanup() {
    print_info "Cleaning up..."
    if [[ -d "downloads" ]]; then
        rm -rf "downloads"
    fi
}

# === MAIN PROGRAM ===
main() {
    # Create downloads directory if it doesn't exist
    mkdir -p downloads
    
    while true; do
        print_header
        print_menu
        
        echo -n "║  Enter choice (1-4): "
        read -r choice
        
        case "$choice" in
            1)
                web_interface
                ;;
            2)
                cli_help
                ;;
            3)
                setup_dependencies
                ;;
            4)
                clear
                print_header
                cleanup
                echo "║  👋 Goodbye! Thank you for using YouTube Downloader.        ║"
                echo "$END"
                exit 0
                ;;
            *)
                print_error "Invalid choice! Please enter a number from 1 to 4."
                sleep 2
                ;;
        esac
    done
}

# Make sure we're in the script directory
cd "$(dirname "$0")"

# Run main program
main "$@"
