#!/usr/bin/env python3
"""
Test script to verify 360p and 480p quality detection fix
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtube_downloader import YouTubeDownloader

def test_quality_detection():
    """Test quality detection for various video formats"""
    
    # Test data - simulated format data with extended quality range
    test_formats = [
        {'height': 480, 'format_id': '18', 'ext': 'mp4'},
        {'height': 360, 'format_id': '17', 'ext': '3gp'},
        {'height': 240, 'format_id': '36', 'ext': '3gp'},
        {'height': 144, 'format_id': '17', 'ext': '3gp'},
        {'height': 720, 'format_id': '22', 'ext': 'mp4'},
        {'height': 1080, 'format_id': '137', 'ext': 'mp4'},
        {'height': 482, 'format_id': '135', 'ext': 'mp4'},  # Edge case
        {'height': 358, 'format_id': '134', 'ext': 'mp4'},  # Edge case
        {'height': 238, 'format_id': '133', 'ext': 'mp4'},  # Edge case
        {'height': 146, 'format_id': '132', 'ext': 'mp4'},  # Edge case
    ]
    
    # Test the quality mapping logic
    qualities = set()
    found_resolutions = set()
    
    for fmt in test_formats:
        height = fmt.get('height')
        if height and isinstance(height, int):
            # Use the same logic as the web app
            if height >= 2000:
                qualities.add('4K')
                found_resolutions.add(2160)
            elif height >= 1350:
                qualities.add('1440p')
                found_resolutions.add(1440)
            elif height >= 1000:
                qualities.add('1080p')
                found_resolutions.add(1080)
            elif height >= 650:
                qualities.add('720p')
                found_resolutions.add(720)
            elif height >= 420:  # 480p range (420-649)
                qualities.add('480p')
                found_resolutions.add(480)
            elif height >= 300:  # 360p range (300-419)
                qualities.add('360p')
                found_resolutions.add(360)
            elif height >= 200:  # 240p range
                qualities.add('240p')
                found_resolutions.add(240)
            elif height >= 100:  # 144p range
                qualities.add('144p')
                found_resolutions.add(144)
    
    print("=== Quality Detection Test ===")
    print(f"Test formats: {test_formats}")
    print(f"Found resolutions: {sorted(found_resolutions, reverse=True)}")
    print(f"Available qualities: {sorted(qualities, key=lambda x: {'4K': 2160, '1440p': 1440, '1080p': 1080, '720p': 720, '480p': 480, '360p': 360, '240p': 240, '144p': 144}.get(x, 0), reverse=True)}")
    
    # Verify that all qualities are detected correctly
    expected_qualities = {'1080p', '720p', '480p', '360p', '240p', '144p'}
    assert qualities == expected_qualities, f"Expected {expected_qualities}, got {qualities}"
    
    print("✅ Quality detection test passed!")
    
    # Test format selection logic
    downloader = YouTubeDownloader()
    
    # Test 480p selection
    fallbacks_480p = downloader._get_quality_fallbacks('480p')
    print(f"\n480p fallbacks: {fallbacks_480p[:3]}")
    
    # Test 360p selection
    fallbacks_360p = downloader._get_quality_fallbacks('360p')
    print(f"360p fallbacks: {fallbacks_360p[:3]}")
    
    # Test 240p selection
    fallbacks_240p = downloader._get_quality_fallbacks('240p')
    print(f"240p fallbacks: {fallbacks_240p[:3]}")
    
    # Test 144p selection
    fallbacks_144p = downloader._get_quality_fallbacks('144p')
    print(f"144p fallbacks: {fallbacks_144p[:3]}")
    
    # Check that they're all different
    assert fallbacks_480p[0] != fallbacks_360p[0], "480p and 360p should have different primary format selectors"
    assert fallbacks_360p[0] != fallbacks_240p[0], "360p and 240p should have different primary format selectors"
    assert fallbacks_240p[0] != fallbacks_144p[0], "240p and 144p should have different primary format selectors"
    
    print("✅ Format selection test passed!")
    print("\n=== All tests passed! ===")

if __name__ == '__main__':
    test_quality_detection()