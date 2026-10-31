
import requests
import os
import urllib.parse
import time
import json

# AllTalk API details
ALLTALK_URL = "http://127.0.0.1:7851"
VOICE = "Clint_Eastwood CC3 (enhanced).wav"
OUTPUT_DIR = "D:/AllTalk/alltalk_tts/outputs"

def test_streaming_endpoint():
    """Test the AllTalk streaming endpoint directly."""
    print("\n=== Testing AllTalk Streaming Endpoint ===")
    
    # Parameters for the request
    params = {
        "text": "This is a test of the streaming API. If you hear this, it's working.",
        "voice": VOICE,
        "language": "en",
        "output_file": f"test_streaming_{int(time.time())}"
    }
    
    # Create the URL with encoded parameters
    url = f"{ALLTALK_URL}/api/tts-generate-streaming"
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    
    print(f"Attempting to access: {full_url}")
    
    # Try the request
    try:
        response = requests.get(full_url, stream=True)
        print(f"Status code: {response.status_code}")
        print(f"Content type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            print("Streaming endpoint appears to be working!")
            
            # Save the first few bytes to check if it's valid audio
            output_file = os.path.join(OUTPUT_DIR, f"{params['output_file']}.wav")
            time.sleep(2)  # Give AllTalk time to generate the file
            
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"Found output file: {output_file}")
                print(f"File size: {file_size} bytes")
                return True
            else:
                print(f"Output file not found at: {output_file}")
                # Check for variations
                for ext in [".wav.wav", ""]:
                    alt_path = os.path.join(OUTPUT_DIR, f"{params['output_file']}{ext}")
                    if os.path.exists(alt_path):
                        print(f"Found alternative output file: {alt_path}")
                        print(f"File size: {os.path.getsize(alt_path)} bytes")
                        return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception occurred: {e}")
        return False

def test_direct_api():
    """Test the AllTalk direct API."""
    print("\n=== Testing AllTalk Direct API ===")
    
    url = f"{ALLTALK_URL}/api/tts"
    data = {
        "text": "This is a test of the direct API. If you hear this, it's working.",
        "voice": VOICE
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("Direct API appears to be working!")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception occurred: {e}")
        return False

def test_get_voices():
    """Test getting available voices."""
    print("\n=== Testing AllTalk Voices Endpoint ===")
    
    url = f"{ALLTALK_URL}/api/voices"
    
    try:
        response = requests.get(url)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            voices = response.json()
            print(f"Found {len(voices)} voices")
            print(f"First voice: {voices[0] if voices else 'None'}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception occurred: {e}")
        return False

def test_file_access():
    """Test direct file access to the AllTalk outputs directory."""
    print("\n=== Testing File Access ===")
    
    if not os.path.exists(OUTPUT_DIR):
        print(f"Error: Output directory does not exist: {OUTPUT_DIR}")
        return False
    
    files = os.listdir(OUTPUT_DIR)
    wav_files = [f for f in files if f.endswith(".wav")]
    
    print(f"Found {len(files)} files in output directory")
    print(f"Found {len(wav_files)} WAV files")
    
    if wav_files:
        first_wav = os.path.join(OUTPUT_DIR, wav_files[0])
        print(f"First WAV file: {wav_files[0]}")
        print(f"File size: {os.path.getsize(first_wav)} bytes")
        return True
    else:
        print("No WAV files found in output directory")
        return False

def create_html_player(wav_files):
    """Create an HTML file with audio players for testing."""
    print("\n=== Creating HTML Test Player ===")
    
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_audio_player.html")
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AllTalk Audio Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .audio-item { margin-bottom: 20px; padding: 10px; border: 1px solid #ccc; border-radius: 5px; }
            .direct-url { word-break: break-all; font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <h1>AllTalk Audio Test</h1>
        <p>Test playing various audio files from AllTalk</p>
        
        <h2>Direct Streaming URL Test</h2>
        <div class="audio-item">
            <p>Testing streaming API (this may not work in browser):</p>
            <p class="direct-url">http://127.0.0.1:7851/api/tts-generate-streaming?text=This%20is%20a%20test%20of%20the%20streaming%20API&voice=Clint_Eastwood%20CC3%20(enhanced).wav&language=en&output_file=test_direct</p>
            <audio controls>
                <source src="http://127.0.0.1:7851/api/tts-generate-streaming?text=This%20is%20a%20test%20of%20the%20streaming%20API&voice=Clint_Eastwood%20CC3%20(enhanced).wav&language=en&output_file=test_direct" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
        
        <h2>Direct File Access Test</h2>
    """
    
    for i, wav_file in enumerate(wav_files[:5]):  # Take first 5 files
        file_url = f"file:///{OUTPUT_DIR}/{wav_file}"
        html_content += f"""
        <div class="audio-item">
            <p>File {i+1}: {wav_file}</p>
            <p class="direct-url">{file_url}</p>
            <audio controls>
                <source src="{file_url}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    with open(html_path, "w") as f:
        f.write(html_content)
    
    print(f"Created HTML player at: {html_path}")
    return html_path

def create_unity_streaming_test():
    """Create a C# test script for Unity to test streaming."""
    print("\n=== Creating Unity Test Script ===")
    
    cs_path = "D:/VRSystemTest/Assets/Scripts/Tests/AudioStreamingTest.cs"
    os.makedirs(os.path.dirname(cs_path), exist_ok=True)
    
    cs_content = """
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;
using System;
using System.IO;

public class AudioStreamingTest : MonoBehaviour
{
    [SerializeField]
    private AudioSource audioSource;
    
    [SerializeField]
    private string testUrl = "http://127.0.0.1:7851/api/tts-generate-streaming?text=This%20is%20a%20test%20of%20the%20streaming%20API&voice=Clint_Eastwood%20CC3%20(enhanced).wav&language=en&output_file=test_unity";
    
    [SerializeField]
    private string testOutputDir = "D:/AllTalk/alltalk_tts/outputs";
    
    [SerializeField]
    private string testOutputFile = "test_unity.wav";
    
    void Start()
    {
        if (audioSource == null)
            audioSource = GetComponent<AudioSource>();
        
        if (audioSource == null)
            audioSource = gameObject.AddComponent<AudioSource>();
    }
    
    public void TestStreamingURL()
    {
        Debug.Log($"Testing streaming URL: {testUrl}");
        StartCoroutine(StreamAudioFromURL());
    }
    
    public void TestDirectFile()
    {
        Debug.Log($"Testing direct file: {Path.Combine(testOutputDir, testOutputFile)}");
        StartCoroutine(LoadAudioFromFile());
    }
    
    private IEnumerator StreamAudioFromURL()
    {
        Debug.Log("Starting StreamAudioFromURL");
        
        // Try the AllTalk streaming URL directly
        using (UnityWebRequest request = UnityWebRequestMultimedia.GetAudioClip(testUrl, AudioType.WAV))
        {
            Debug.Log("Created web request");
            
            // Set timeout
            request.timeout = 30;
            
            // Set headers
            request.SetRequestHeader("Accept", "audio/*");
            
            // Create a new download handler
            DownloadHandlerAudioClip audioHandler = new DownloadHandlerAudioClip(testUrl, AudioType.WAV);
            audioHandler.streamAudio = true;
            
            // Set the download handler
            request.downloadHandler = audioHandler;
            
            Debug.Log("Sending request...");
            yield return request.SendWebRequest();
            
            if (request.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Streaming error: {request.error}");
            }
            else
            {
                Debug.Log("Request completed successfully");
                AudioClip clip = DownloadHandlerAudioClip.GetContent(request);
                
                if (clip != null)
                {
                    Debug.Log($"Received audio clip: {clip.length}s, {clip.frequency}Hz, {clip.channels} channels, state: {clip.loadState}");
                    
                    // Ensure the clip has loaded
                    while (clip.loadState == AudioDataLoadState.Loading)
                    {
                        Debug.Log("Waiting for clip to load...");
                        yield return new WaitForSeconds(0.1f);
                    }
                    
                    if (clip.loadState == AudioDataLoadState.Loaded)
                    {
                        clip.name = "TestStreamingClip";
                        audioSource.clip = clip;
                        audioSource.Play();
                        Debug.Log("Started playback");
                    }
                    else
                    {
                        Debug.LogError($"Clip failed to load: {clip.loadState}");
                    }
                }
                else
                {
                    Debug.LogError("Failed to get AudioClip from response");
                }
            }
        }
    }
    
    private IEnumerator LoadAudioFromFile()
    {
        Debug.Log("Starting LoadAudioFromFile");
        
        // Wait for file to be created by AllTalk
        yield return new WaitForSeconds(2f);
        
        string filePath = Path.Combine(testOutputDir, testOutputFile);
        
        if (!File.Exists(filePath))
        {
            Debug.LogError($"File does not exist: {filePath}");
            
            // Try finding the file with different extensions
            string[] extensions = new[] { "", ".wav", ".wav.wav" };
            foreach (string ext in extensions)
            {
                string altPath = Path.Combine(testOutputDir, $"test_unity{ext}");
                if (File.Exists(altPath))
                {
                    Debug.Log($"Found alternative file: {altPath}");
                    filePath = altPath;
                    break;
                }
            }
            
            if (!File.Exists(filePath))
            {
                Debug.LogError("Could not find any matching file");
                yield break;
            }
        }
        
        // Convert to URI for Unity
        string uri = new Uri(filePath).AbsoluteUri;
        Debug.Log($"Loading from URI: {uri}");
        
        using (UnityWebRequest request = UnityWebRequestMultimedia.GetAudioClip(uri, AudioType.WAV))
        {
            yield return request.SendWebRequest();
            
            if (request.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Error loading file: {request.error}");
            }
            else
            {
                AudioClip clip = DownloadHandlerAudioClip.GetContent(request);
                
                if (clip != null)
                {
                    Debug.Log($"Loaded audio clip: {clip.length}s, {clip.frequency}Hz, {clip.channels} channels");
                    
                    clip.name = "TestFileClip";
                    audioSource.clip = clip;
                    audioSource.Play();
                    Debug.Log("Started playback");
                }
                else
                {
                    Debug.LogError("Failed to get AudioClip from file");
                }
            }
        }
    }
}
"""
    
    with open(cs_path, "w") as f:
        f.write(cs_content)
    
    # Create a simple test scene script
    scene_path = "D:/VRSystemTest/Assets/Scripts/Tests/AudioStreamingTestScene.cs"
    
    scene_content = """
using UnityEngine;
using UnityEngine.UI;
using System.Collections;

public class AudioStreamingTestScene : MonoBehaviour
{
    public AudioStreamingTest streamingTest;
    public Button btnTestStreaming;
    public Button btnTestFile;
    public Text statusText;
    
    void Start()
    {
        if (streamingTest == null)
            streamingTest = FindObjectOfType<AudioStreamingTest>();
        
        if (btnTestStreaming != null)
        {
            btnTestStreaming.onClick.AddListener(() => {
                if (statusText != null) statusText.text = "Testing streaming...";
                streamingTest.TestStreamingURL();
                StartCoroutine(UpdateStatusAfterDelay("Streaming test complete"));
            });
        }
        
        if (btnTestFile != null)
        {
            btnTestFile.onClick.AddListener(() => {
                if (statusText != null) statusText.text = "Testing direct file...";
                streamingTest.TestDirectFile();
                StartCoroutine(UpdateStatusAfterDelay("File test complete"));
            });
        }
    }
    
    private IEnumerator UpdateStatusAfterDelay(string message)
    {
        yield return new WaitForSeconds(5f);
        if (statusText != null) statusText.text = message;
    }
}
"""
    
    with open(scene_path, "w") as f:
        f.write(scene_content)
    
    print(f"Created Unity test scripts at: {cs_path} and {scene_path}")
    return cs_path

if __name__ == "__main__":
    print("=== AllTalk Streaming Test ===")
    
    # Test various aspects of AllTalk
    test_streaming_endpoint()
    test_direct_api()
    test_get_voices()
    test_file_access()
    
    # Create HTML player for manual testing
    if os.path.exists(OUTPUT_DIR):
        wav_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".wav")]
        if wav_files:
            create_html_player(wav_files)
    
    # Create Unity test script
    create_unity_streaming_test()
