package com.mirmedialabs.app;

import java.math.BigInteger;
import java.security.MessageDigest;
import java.util.Arrays;

/**
 * Ed25519 signature VERIFICATION only (RFC 8032 §5.1.7), pure Java, for Android 7+ (the platform has no
 * Ed25519 before API 33). Used to check update manifests signed with the MirCorp update key — the same
 * key and scheme as the PC edition's updates (installer/build_tool.py, server/pcupdate.py).
 * BigInteger + extended coordinates: slow by crypto standards (~20 ms) and that's fine for one manifest.
 */
final class Ed25519 {
    private static final BigInteger P = BigInteger.ONE.shiftLeft(255).subtract(BigInteger.valueOf(19));
    private static final BigInteger L = BigInteger.ONE.shiftLeft(252).add(new BigInteger("27742317777372353535851937790883648493"));
    private static final BigInteger D = BigInteger.valueOf(-121665).multiply(BigInteger.valueOf(121666).modInverse(P)).mod(P);
    private static final BigInteger D2 = D.add(D).mod(P);
    private static final BigInteger SQRT_M1 = BigInteger.valueOf(2).modPow(P.subtract(BigInteger.ONE).shiftRight(2), P);
    private static final BigInteger[] B;
    static {
        BigInteger by = BigInteger.valueOf(4).multiply(BigInteger.valueOf(5).modInverse(P)).mod(P);
        BigInteger bx = recoverX(by, 0);
        B = new BigInteger[]{bx, by, BigInteger.ONE, bx.multiply(by).mod(P)};
    }

    private Ed25519() {}

    /** true only for a valid signature of msg under the 32-byte public key. Never throws. */
    static boolean verify(byte[] pub, byte[] msg, byte[] sig) {
        try {
            if (pub == null || sig == null || msg == null || pub.length != 32 || sig.length != 64) return false;
            BigInteger[] a = decode(pub);
            byte[] rb = Arrays.copyOfRange(sig, 0, 32);
            BigInteger[] r = decode(rb);
            if (a == null || r == null) return false;
            BigInteger s = le(Arrays.copyOfRange(sig, 32, 64));
            if (s.compareTo(L) >= 0) return false;
            MessageDigest sha = MessageDigest.getInstance("SHA-512");
            sha.update(rb); sha.update(pub); sha.update(msg);
            BigInteger k = le(sha.digest()).mod(L);
            BigInteger[] sB = mul(s, B);
            BigInteger[] rkA = add(r, mul(k, a));
            return eq(sB, rkA);
        } catch (Exception e) {
            return false;
        }
    }

    private static BigInteger le(byte[] b) {
        byte[] r = new byte[b.length + 1];
        for (int i = 0; i < b.length; i++) r[b.length - i] = b[i];
        return new BigInteger(r);
    }

    private static BigInteger recoverX(BigInteger y, int sign) {
        if (y.compareTo(P) >= 0) return null;
        BigInteger y2 = y.multiply(y).mod(P);
        BigInteger x2 = y2.subtract(BigInteger.ONE).multiply(D.multiply(y2).add(BigInteger.ONE).modInverse(P)).mod(P);
        if (x2.signum() == 0) return sign == 1 ? null : BigInteger.ZERO;
        BigInteger x = x2.modPow(P.add(BigInteger.valueOf(3)).shiftRight(3), P);
        if (x.multiply(x).subtract(x2).mod(P).signum() != 0) x = x.multiply(SQRT_M1).mod(P);
        if (x.multiply(x).subtract(x2).mod(P).signum() != 0) return null;
        if (x.testBit(0) != (sign == 1)) x = P.subtract(x);
        return x;
    }

    private static BigInteger[] decode(byte[] s) {
        byte[] c = s.clone();
        int sign = (c[31] >> 7) & 1;
        c[31] &= 0x7F;
        BigInteger y = le(c);
        BigInteger x = recoverX(y, sign);
        if (x == null) return null;
        return new BigInteger[]{x, y, BigInteger.ONE, x.multiply(y).mod(P)};
    }

    private static BigInteger[] add(BigInteger[] p, BigInteger[] q) {
        BigInteger a = p[1].subtract(p[0]).multiply(q[1].subtract(q[0])).mod(P);
        BigInteger b = p[1].add(p[0]).multiply(q[1].add(q[0])).mod(P);
        BigInteger c = p[3].multiply(D2).multiply(q[3]).mod(P);
        BigInteger d = p[2].shiftLeft(1).multiply(q[2]).mod(P);
        BigInteger e = b.subtract(a), f = d.subtract(c), g = d.add(c), h = b.add(a);
        return new BigInteger[]{e.multiply(f).mod(P), g.multiply(h).mod(P), f.multiply(g).mod(P), e.multiply(h).mod(P)};
    }

    private static BigInteger[] mul(BigInteger s, BigInteger[] pt) {
        BigInteger[] q = {BigInteger.ZERO, BigInteger.ONE, BigInteger.ONE, BigInteger.ZERO};
        for (int i = s.bitLength() - 1; i >= 0; i--) {
            q = add(q, q);
            if (s.testBit(i)) q = add(q, pt);
        }
        return q;
    }

    private static boolean eq(BigInteger[] p, BigInteger[] q) {
        return p[0].multiply(q[2]).subtract(q[0].multiply(p[2])).mod(P).signum() == 0
                && p[1].multiply(q[2]).subtract(q[1].multiply(p[2])).mod(P).signum() == 0;
    }
}
