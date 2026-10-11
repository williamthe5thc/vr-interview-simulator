using System;

/// One entry of the mouth-shape timeline the server sends for each voice chunk (Rhubarb shapes A-H, X).
/// s / e = start / end seconds from the start of the chunk's audio; v = the shape letter.
[Serializable]
public class MouthCue
{
    public float s;
    public float e;
    public string v;
}
