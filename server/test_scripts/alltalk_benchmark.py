#!/usr/bin/env python3
"""
AllTalk Voice Benchmark Tool

This script tests all available AllTalk voices with different text lengths
to determine processing time, helping optimize timeout settings.
"""

import os
import sys
import json
import time
import requests
import concurrent.futures
import argparse
import logging
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from tabulate import tabulate  # pip install tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alltalk_benchmark.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("alltalk_benchmark")

class AllTalkVoiceBenchmark:
    def __init__(self, 
                 base_url="http://127.0.0.1:7851", 
                 output_dir="benchmark_results", 
                 save_audio=False,
                 concurrent=False):
        self.base_url = base_url.rstrip('/')
        self.output_dir = output_dir
        self.save_audio = save_audio
        self.concurrent = concurrent
        self.voices = []
        self.results = []
        self.successful_benchmarks = 0
        self.failed_benchmarks = 0
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Test texts of varying lengths
        self.test_texts = {
            "short": "Hello, how are you today?",
            "medium": "Welcome to the interview simulation. I'll be asking you a series of questions about your experience and qualifications for this position.",
            "long": "I notice from your resume that you have experience with Python programming. Could you tell me about a challenging project where you used Python to solve a complex problem? I'm particularly interested in your approach to the problem, the techniques you used, and the results you achieved.",
            "very_long": """Let's discuss a hypothetical scenario. Imagine you're tasked with building a real-time analytics dashboard for a large e-commerce platform. This dashboard needs to show metrics like current active users, sales in the last hour, inventory levels, and customer service response times. The data comes from multiple microservices, and the dashboard needs to update in real-time with minimal latency.

How would you architect this solution? Please consider aspects like data collection, processing, storage, and presentation. What technologies would you use? How would you ensure the system remains responsive even during high-traffic periods? What monitoring and alerting would you put in place?

Also, please discuss any potential challenges you foresee with this implementation and how you would address them. I'm interested in understanding your thought process and problem-solving approach."""
        }
        
    def check_server(self) -> bool:
        """Check if AllTalk server is running and responsive"""
        try:
            logger.info(f"Checking AllTalk server at {self.base_url}")
            response = requests.get(f"{self.base_url}/api/ready", timeout=5)
            
            if response.status_code == 200:
                logger.info("Server is responsive")
                return True
            else:
                logger.error(f"Server returned status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
    
    def get_available_voices(self) -> List[str]:
        """Get list of available voices from the server"""
        try:
            response = requests.get(f"{self.base_url}/api/voices", timeout=5)
            if response.status_code == 200:
                data = response.json()
                voices = data.get('voices', [])
                logger.info(f"Found {len(voices)} voices")
                return voices
            else:
                logger.error(f"Failed to get voices: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting voices: {e}")
            return []
    
    def scan_voices_directory(self, alltalk_dir="D:/AllTalk/alltalk_tts") -> List[str]:
        """Scan voices directory for .wav files as a backup method"""
        voices_dir = os.path.join(alltalk_dir, "voices")
        if not os.path.exists(voices_dir):
            logger.error(f"Voices directory not found: {voices_dir}")
            return []
            
        voice_files = []
        try:
            for file in os.listdir(voices_dir):
                if file.endswith('.wav'):
                    voice_files.append(file)
                    
            logger.info(f"Found {len(voice_files)} voice files in directory")
            return voice_files
        except Exception as e:
            logger.error(f"Error scanning voices directory: {e}")
            return []
    
    def benchmark_voice(self, voice: str, text_name: str, text: str) -> Dict[str, Any]:
        """Benchmark a single voice with a specific text"""
        result = {
            "voice": voice,
            "text_name": text_name,
            "text_length": len(text),
            "success": False,
            "time_taken": None,
            "error": None,
            "file_size": None,
            "test_time": datetime.now().isoformat()
        }
        
        logger.info(f"Testing voice '{voice}' with {text_name} text ({len(text)} chars)")
        
        start_time = time.time()
        
        try:
            output_file = f"test_{voice.replace(' ', '_').replace('.', '_')}_{text_name}_{int(time.time())}"
            
            # Try tts-generate API
            response = requests.post(
                f"{self.base_url}/api/tts-generate",
                data={
                    "text_input": text,
                    "character_voice_gen": voice,
                    "output_file_name": output_file,
                    "format": "wav"
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=300  # 5 minutes timeout for long texts
            )
            
            end_time = time.time()
            result["time_taken"] = end_time - start_time
            
            if response.status_code == 200:
                result["success"] = True
                result["file_size"] = len(response.content)
                
                # Save audio file if requested
                if self.save_audio:
                    try:
                        save_path = os.path.join(self.output_dir, f"{output_file}.wav")
                        with open(save_path, "wb") as f:
                            f.write(response.content)
                        logger.info(f"Saved audio to {save_path}")
                    except Exception as e:
                        logger.warning(f"Failed to save audio file: {e}")
                
                logger.info(f"Successfully tested voice '{voice}': {result['time_taken']:.2f} seconds")
                self.successful_benchmarks += 1
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to test voice '{voice}': {result['error']}")
                self.failed_benchmarks += 1
                
        except Exception as e:
            end_time = time.time()
            result["time_taken"] = end_time - start_time
            result["error"] = str(e)
            logger.error(f"Exception testing voice '{voice}': {e}")
            self.failed_benchmarks += 1
            
        return result
    
    def run_benchmarks(self):
        """Run benchmarks on all available voices with all text lengths"""
        if not self.check_server():
            logger.error("Cannot connect to AllTalk server. Exiting.")
            return False
            
        # Get available voices
        self.voices = self.get_available_voices()
        
        # If no voices from API, try directory scan
        if not self.voices:
            logger.warning("No voices found from API, scanning directory...")
            self.voices = self.scan_voices_directory()
            
        if not self.voices:
            logger.error("No voices found. Cannot run benchmarks.")
            return False
            
        logger.info(f"Starting benchmarks with {len(self.voices)} voices and {len(self.test_texts)} text samples")
        print(f"\nRunning benchmarks with {len(self.voices)} voices...")
        
        start_time = time.time()
        self.results = []
        
        if self.concurrent:
            # Run benchmarks concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                
                for voice in self.voices:
                    for text_name, text in self.test_texts.items():
                        futures.append(
                            executor.submit(self.benchmark_voice, voice, text_name, text)
                        )
                
                for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                    result = future.result()
                    self.results.append(result)
                    # Display progress
                    total = len(self.voices) * len(self.test_texts)
                    print(f"\rProgress: {i}/{total} ({i/total*100:.1f}%)", end="", flush=True)
                    
                print()  # New line after progress display
                
        else:
            # Run benchmarks sequentially
            total = len(self.voices) * len(self.test_texts)
            count = 0
            
            for voice in self.voices:
                for text_name, text in self.test_texts.items():
                    result = self.benchmark_voice(voice, text_name, text)
                    self.results.append(result)
                    
                    # Display progress
                    count += 1
                    print(f"\rProgress: {count}/{total} ({count/total*100:.1f}%)", end="", flush=True)
                    
            print()  # New line after progress display
                    
        end_time = time.time()
        total_time = end_time - start_time
        
        logger.info(f"Completed benchmarks in {total_time:.2f} seconds")
        logger.info(f"Successful: {self.successful_benchmarks}, Failed: {self.failed_benchmarks}")
        
        # Generate report
        self.generate_report()
        
        return True
        
    def generate_report(self):
        """Generate benchmark report"""
        if not self.results:
            logger.warning("No results to report")
            return
            
        # Create report filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.output_dir, f"voice_benchmark_report_{timestamp}.json")
        html_report = os.path.join(self.output_dir, f"voice_benchmark_report_{timestamp}.html")
        
        # Save raw results to JSON
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        logger.info(f"Saved results to {report_file}")
        
        # Process results for reporting
        voice_stats = {}
        for result in self.results:
            voice = result["voice"]
            text_name = result["text_name"]
            
            if voice not in voice_stats:
                voice_stats[voice] = {
                    "short": None,
                    "medium": None,
                    "long": None,
                    "very_long": None,
                    "success_rate": 0,
                    "total_tests": 0
                }
                
            voice_stats[voice]["total_tests"] += 1
            
            if result["success"]:
                voice_stats[voice]["success_rate"] += 1
                voice_stats[voice][text_name] = result["time_taken"]
                
        # Calculate success rate percentage
        for voice in voice_stats:
            if voice_stats[voice]["total_tests"] > 0:
                voice_stats[voice]["success_rate"] = (voice_stats[voice]["success_rate"] / voice_stats[voice]["total_tests"]) * 100
                
        # Generate simple table for console display
        print("\n=== Voice Benchmark Results ===\n")
        
        # Prepare table data
        table_data = []
        headers = ["Voice", "Short (s)", "Medium (s)", "Long (s)", "Very Long (s)", "Success Rate"]
        
        for voice, stats in voice_stats.items():
            row = [
                voice,
                f"{stats['short']:.2f}" if stats['short'] else "N/A",
                f"{stats['medium']:.2f}" if stats['medium'] else "N/A",
                f"{stats['long']:.2f}" if stats['long'] else "N/A",
                f"{stats['very_long']:.2f}" if stats['very_long'] else "N/A",
                f"{stats['success_rate']:.1f}%"
            ]
            table_data.append(row)
            
        # Sort by success rate (descending) and then by Very Long processing time (ascending)
        table_data.sort(key=lambda x: (-float(x[5].replace('%', '')), 
                                       float(x[4].replace('N/A', '999'))))
        
        # Print table
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Calculate overall stats
        successful_results = [r for r in self.results if r["success"]]
        if successful_results:
            avg_time = statistics.mean([r["time_taken"] for r in successful_results])
            max_time = max([r["time_taken"] for r in successful_results])
            
            print(f"\nOverall Statistics:")
            print(f"Average Processing Time: {avg_time:.2f} seconds")
            print(f"Maximum Processing Time: {max_time:.2f} seconds")
            print(f"Success Rate: {(len(successful_results) / len(self.results)) * 100:.1f}%")
        
        # Generate recommended timeout settings
        timeouts = self.recommend_timeouts()
        print("\nRecommended Timeout Settings:")
        print(f"  timeout: {timeouts['timeout']} seconds")
        print(f"  direct_api_timeout: {timeouts['direct_api_timeout']} seconds")
        
        # Generate HTML report
        self.generate_html_report(html_report, voice_stats, timeouts)
        print(f"\nHTML report saved to: {html_report}")
        
        return voice_stats
    
    def recommend_timeouts(self) -> Dict[str, int]:
        """Calculate recommended timeout settings based on benchmark results"""
        successful_results = [r for r in self.results if r["success"]]
        
        if not successful_results:
            return {
                "timeout": 60,
                "direct_api_timeout": 90
            }
            
        # Calculate percentiles for different text lengths
        very_long_times = [r["time_taken"] for r in successful_results if r["text_name"] == "very_long"]
        long_times = [r["time_taken"] for r in successful_results if r["text_name"] == "long"]
        medium_times = [r["time_taken"] for r in successful_results if r["text_name"] == "medium"]
        
        # Use the 90th percentile of processing times with padding
        if very_long_times:
            very_long_p90 = sorted(very_long_times)[min(len(very_long_times)-1, int(len(very_long_times) * 0.9))]
            direct_api_timeout = int(very_long_p90 * 1.5)  # 50% buffer
        elif long_times:
            long_p90 = sorted(long_times)[min(len(long_times)-1, int(len(long_times) * 0.9))]
            direct_api_timeout = int(long_p90 * 2.0)  # 100% buffer for long texts
        else:
            direct_api_timeout = 90  # Default fallback
            
        # For standard timeout, use medium or long texts
        if medium_times:
            medium_p90 = sorted(medium_times)[min(len(medium_times)-1, int(len(medium_times) * 0.9))]
            timeout = int(medium_p90 * 1.5)  # 50% buffer
        elif long_times:
            timeout = int(min(long_times) * 1.2)  # 20% buffer for minimum long time
        else:
            timeout = 60  # Default fallback
            
        # Ensure minimum reasonable values
        timeout = max(timeout, 30)
        direct_api_timeout = max(direct_api_timeout, timeout + 30)
        
        return {
            "timeout": timeout,
            "direct_api_timeout": direct_api_timeout
        }
        
    def generate_html_report(self, filename, voice_stats, timeouts):
        """Generate HTML report with interactive charts"""
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllTalk Voice Benchmark Results</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
        }
        h1, h2 {
            color: #2c3e50;
        }
        .card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .chart-container {
            height: 400px;
            margin: 20px 0;
        }
        .recommendations {
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-left: 4px solid #2196F3;
        }
        .success {
            color: #28a745;
        }
        .warning {
            color: #ffc107;
        }
        .danger {
            color: #dc3545;
        }
    </style>
</head>
<body>
    <h1>AllTalk Voice Benchmark Results</h1>
    <p>Generated on: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
    
    <div class="card">
        <h2>Recommended Timeout Settings</h2>
        <div class="recommendations">
            <p><strong>timeout:</strong> """ + str(timeouts["timeout"]) + """ seconds</p>
            <p><strong>direct_api_timeout:</strong> """ + str(timeouts["direct_api_timeout"]) + """ seconds</p>
        </div>
        <p>These settings include safety margins to handle the majority of voice generation requests.</p>
    </div>
    
    <div class="card">
        <h2>Performance by Voice</h2>
        <div class="chart-container">
            <canvas id="voiceComparisonChart"></canvas>
        </div>
    </div>
    
    <div class="card">
        <h2>Text Length Impact</h2>
        <div class="chart-container">
            <canvas id="textLengthChart"></canvas>
        </div>
    </div>
    
    <div class="card">
        <h2>Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Voice</th>
                    <th>Short (s)</th>
                    <th>Medium (s)</th>
                    <th>Long (s)</th>
                    <th>Very Long (s)</th>
                    <th>Success Rate</th>
                </tr>
            </thead>
            <tbody>
"""
        
        # Add table rows
        for voice, stats in sorted(voice_stats.items(), key=lambda x: (-x[1]["success_rate"], 
                                                                     x[1]["very_long"] or 999)):
            success_class = "success" if stats["success_rate"] > 90 else "warning" if stats["success_rate"] > 50 else "danger"
            
            html_content += f"""
                <tr>
                    <td>{voice}</td>
                    <td>{f"{stats['short']:.2f}" if stats['short'] else "N/A"}</td>
                    <td>{f"{stats['medium']:.2f}" if stats['medium'] else "N/A"}</td>
                    <td>{f"{stats['long']:.2f}" if stats['long'] else "N/A"}</td>
                    <td>{f"{stats['very_long']:.2f}" if stats['very_long'] else "N/A"}</td>
                    <td class="{success_class}">{stats['success_rate']:.1f}%</td>
                </tr>"""
        
        # Calculate overall statistics
        successful_voices = sum(1 for v in voice_stats.values() if v["success_rate"] > 0)
        total_voices = len(voice_stats)
        
        # Continue with the HTML template
        html_content += """
            </tbody>
        </table>
    </div>
    
    <div class="card">
        <h2>Summary Statistics</h2>
        <ul>
            <li><strong>Successful Voices:</strong> """ + str(successful_voices) + " of " + str(total_voices) + """</li>
            <li><strong>Overall Success Rate:</strong> """ + f"{(successful_voices / total_voices * 100) if total_voices > 0 else 0:.1f}%" + """</li>
        </ul>
    </div>
    
    <script>
        // Prepare data for the charts
        const voiceStats = """ + json.dumps(voice_stats) + """;
        
        // Voice comparison chart
        const voiceCtx = document.getElementById('voiceComparisonChart').getContext('2d');
        const voiceLabels = Object.keys(voiceStats);
        const shortData = [];
        const mediumData = [];
        const longData = [];
        const veryLongData = [];
        
        for (const voice in voiceStats) {
            shortData.push(voiceStats[voice].short);
            mediumData.push(voiceStats[voice].medium);
            longData.push(voiceStats[voice].long);
            veryLongData.push(voiceStats[voice].very_long);
        }
        
        new Chart(voiceCtx, {
            type: 'bar',
            data: {
                labels: voiceLabels,
                datasets: [
                    {
                        label: 'Short Text',
                        data: shortData,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Medium Text',
                        data: mediumData,
                        backgroundColor: 'rgba(75, 192, 192, 0.5)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Long Text',
                        data: longData,
                        backgroundColor: 'rgba(255, 159, 64, 0.5)',
                        borderColor: 'rgba(255, 159, 64, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Very Long Text',
                        data: veryLongData,
                        backgroundColor: 'rgba(255, 99, 132, 0.5)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Processing Time (seconds)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Voice'
                        }
                    }
                }
            }
        });
        
        // Text length impact chart
        const textCtx = document.getElementById('textLengthChart').getContext('2d');
        
        // Calculate averages by text length
        const textLengths = ['short', 'medium', 'long', 'very_long'];
        const textLengthLabels = ['Short', 'Medium', 'Long', 'Very Long'];
        const avgTimes = [];
        const successRates = [];
        
        for (const length of textLengths) {
            let sum = 0;
            let count = 0;
            let successes = 0;
            
            for (const voice in voiceStats) {
                if (voiceStats[voice][length] !== null) {
                    sum += voiceStats[voice][length];
                    count++;
                    successes++;
                }
            }
            
            avgTimes.push(count > 0 ? sum / count : null);
            successRates.push(voiceLabels.length > 0 ? (successes / voiceLabels.length) * 100 : 0);
        }
        
        new Chart(textCtx, {
            type: 'bar',
            data: {
                labels: textLengthLabels,
                datasets: [
                    {
                        label: 'Average Processing Time (seconds)',
                        data: avgTimes,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Success Rate (%)',
                        data: successRates,
                        backgroundColor: 'rgba(75, 192, 192, 0.5)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1,
                        type: 'line',
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Avg. Processing Time (seconds)'
                        }
                    },
                    y1: {
                        beginAtZero: true,
                        max: 100,
                        position: 'right',
                        grid: {
                            drawOnChartArea: false
                        },
                        title: {
                            display: true,
                            text: 'Success Rate (%)'
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""
        
        # Save HTML report
        with open(filename, 'w') as f:
            f.write(html_content)

def main():
    parser = argparse.ArgumentParser(description="AllTalk Voice Benchmark Tool")
    parser.add_argument("--url", default="http://127.0.0.1:7851", help="AllTalk server URL")
    parser.add_argument("--output", default="benchmark_results", help="Output directory for benchmark results")
    parser.add_argument("--save-audio", action="store_true", help="Save generated audio files")
    parser.add_argument("--concurrent", action="store_true", help="Run benchmarks concurrently (faster but may affect results)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("AllTalk Voice Benchmark Tool")
    print("=" * 60)
    print(f"Server URL: {args.url}")
    print(f"Output directory: {args.output}")
    print(f"Save audio: {args.save_audio}")
    print(f"Concurrent execution: {args.concurrent}")
    print("=" * 60)
    
    benchmark = AllTalkVoiceBenchmark(
        base_url=args.url,
        output_dir=args.output,
        save_audio=args.save_audio,
        concurrent=args.concurrent
    )
    
    # Run benchmarks
    print("\nStarting voice benchmarks. This may take several minutes...")
    benchmark.run_benchmarks()
    
    print("\nBenchmark complete! Check the output directory for detailed reports.")

if __name__ == "__main__":
    try:
        from tabulate import tabulate
    except ImportError:
        print("Installing tabulate package...")
        import pip
        pip.main(['install', 'tabulate'])
        from tabulate import tabulate
        
    main()